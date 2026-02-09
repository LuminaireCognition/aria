"""
Tests for Route Result Construction.

Tests security summary computation, warning generation, and threat level assessment.
"""

from __future__ import annotations

import pytest

from tests.mcp.conftest import create_mock_universe, STANDARD_SYSTEMS, STANDARD_EDGES


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def standard_universe():
    """Standard 6-system universe for result builder tests."""
    return create_mock_universe(STANDARD_SYSTEMS, STANDARD_EDGES)


# =============================================================================
# Security Summary Tests
# =============================================================================


class TestComputeSecuritySummary:
    """Test compute_security_summary function."""

    def test_pure_highsec_route(self, standard_universe):
        """Highsec route has correct breakdown."""
        from aria_esi.services.navigation.result_builder import compute_security_summary

        # Jita (0) -> Perimeter (1) - both highsec
        path = [0, 1]
        summary = compute_security_summary(standard_universe, path)

        assert summary.total_jumps == 1
        assert summary.highsec_jumps == 2  # Both systems are highsec
        assert summary.lowsec_jumps == 0
        assert summary.nullsec_jumps == 0

    def test_mixed_security_route(self, standard_universe):
        """Mixed security route has correct breakdown."""
        from aria_esi.services.navigation.result_builder import compute_security_summary

        # Jita (0) -> Maurasi (2) -> Sivala (4) -> Ala (5)
        # Highsec -> Highsec -> Lowsec -> Nullsec
        path = [0, 2, 4, 5]
        summary = compute_security_summary(standard_universe, path)

        assert summary.total_jumps == 3
        assert summary.highsec_jumps == 2  # Jita, Maurasi
        assert summary.lowsec_jumps == 1  # Sivala
        assert summary.nullsec_jumps == 1  # Ala

    def test_lowest_security_tracking(self, standard_universe):
        """Tracks lowest security system correctly."""
        from aria_esi.services.navigation.result_builder import compute_security_summary

        # Route through Ala (nullsec, -0.2)
        path = [0, 2, 4, 5]
        summary = compute_security_summary(standard_universe, path)

        assert summary.lowest_security == pytest.approx(-0.2, abs=0.01)
        assert summary.lowest_security_system == "Ala"

    def test_single_system_path(self, standard_universe):
        """Single system path has zero jumps."""
        from aria_esi.services.navigation.result_builder import compute_security_summary

        path = [0]  # Just Jita
        summary = compute_security_summary(standard_universe, path)

        assert summary.total_jumps == 0
        assert summary.highsec_jumps == 1


# =============================================================================
# Warning Generation Tests
# =============================================================================


class TestGenerateWarnings:
    """Test generate_warnings function."""

    def test_no_warnings_for_highsec_route(self, standard_universe):
        """Pure highsec route generates no warnings."""
        from aria_esi.services.navigation.result_builder import generate_warnings

        path = [0, 1]  # Jita -> Perimeter
        warnings = generate_warnings(standard_universe, path, mode="shortest")

        # No security transitions in highsec
        assert not any("low/null-sec" in w for w in warnings)

    def test_lowsec_entry_warning(self, standard_universe):
        """Route entering lowsec generates warning."""
        from aria_esi.services.navigation.result_builder import generate_warnings

        path = [0, 2, 4]  # Jita -> Maurasi -> Sivala (lowsec)
        warnings = generate_warnings(standard_universe, path, mode="shortest")

        assert any("low/null-sec" in w for w in warnings)

    def test_safe_mode_unavailable_warning(self, standard_universe):
        """Safe mode warns when forced through dangerous space."""
        from aria_esi.services.navigation.result_builder import generate_warnings

        path = [0, 2, 4, 5]  # Must go through lowsec/nullsec
        warnings = generate_warnings(standard_universe, path, mode="safe")

        assert any("No fully high-sec route" in w for w in warnings)


# =============================================================================
# Threat Level Tests
# =============================================================================


class TestGetThreatLevel:
    """Test get_threat_level function."""

    def test_minimal_threat_highsec_only(self):
        """Pure highsec route has minimal threat."""
        from aria_esi.services.navigation.result_builder import get_threat_level

        level = get_threat_level(high_sec=5, low_sec=0, null_sec=0, lowest_sec=0.95)

        assert level == "MINIMAL"

    def test_elevated_threat_borderline(self):
        """Route with 0.5 security has elevated threat."""
        from aria_esi.services.navigation.result_builder import get_threat_level

        level = get_threat_level(high_sec=5, low_sec=0, null_sec=0, lowest_sec=0.50)

        assert level == "ELEVATED"

    def test_high_threat_lowsec(self):
        """Route with lowsec has high threat."""
        from aria_esi.services.navigation.result_builder import get_threat_level

        level = get_threat_level(high_sec=3, low_sec=2, null_sec=0, lowest_sec=0.35)

        assert level == "HIGH"

    def test_critical_threat_nullsec(self):
        """Route with nullsec has critical threat."""
        from aria_esi.services.navigation.result_builder import get_threat_level

        level = get_threat_level(high_sec=3, low_sec=1, null_sec=1, lowest_sec=-0.2)

        assert level == "CRITICAL"

    def test_critical_overrides_high(self):
        """Nullsec presence overrides lowsec for threat level."""
        from aria_esi.services.navigation.result_builder import get_threat_level

        # Even with many lowsec systems, nullsec makes it critical
        level = get_threat_level(high_sec=1, low_sec=10, null_sec=1, lowest_sec=-0.5)

        assert level == "CRITICAL"


# =============================================================================
# Security Summary Dataclass Tests
# =============================================================================


class TestSecuritySummary:
    """Test SecuritySummary dataclass."""

    def test_dataclass_fields(self):
        """SecuritySummary has all required fields."""
        from aria_esi.services.navigation.result_builder import SecuritySummary

        summary = SecuritySummary(
            total_jumps=5,
            highsec_jumps=3,
            lowsec_jumps=1,
            nullsec_jumps=1,
            lowest_security=-0.2,
            lowest_security_system="Ala",
        )

        assert summary.total_jumps == 5
        assert summary.highsec_jumps == 3
        assert summary.lowsec_jumps == 1
        assert summary.nullsec_jumps == 1
        assert summary.lowest_security == -0.2
        assert summary.lowest_security_system == "Ala"
