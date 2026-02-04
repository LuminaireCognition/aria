"""
Tests for Route Weight Computation.

Tests the weight computation functions used by the navigation router
for different routing modes (shortest, safe, unsafe).
"""

from __future__ import annotations

import pytest

from tests.mcp.conftest import create_mock_universe, STANDARD_SYSTEMS, STANDARD_EDGES


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def standard_universe():
    """Standard 6-system universe for weight tests."""
    return create_mock_universe(STANDARD_SYSTEMS, STANDARD_EDGES)


# =============================================================================
# Constants Tests
# =============================================================================


class TestWeightConstants:
    """Test weight constant definitions."""

    def test_security_thresholds(self):
        """Security thresholds are defined correctly."""
        from aria_esi.services.navigation.weights import (
            HIGHSEC_THRESHOLD,
            LOWSEC_THRESHOLD,
        )

        assert HIGHSEC_THRESHOLD == 0.45
        assert LOWSEC_THRESHOLD == 0.0

    def test_safe_mode_weights(self):
        """Safe mode weights are defined."""
        from aria_esi.services.navigation.weights import (
            WEIGHT_NORMAL,
            WEIGHT_LOWSEC_ENTRY,
            WEIGHT_LOWSEC_STAY,
            WEIGHT_NULLSEC,
        )

        assert WEIGHT_NORMAL == 1.0
        assert WEIGHT_LOWSEC_ENTRY == 50.0
        assert WEIGHT_LOWSEC_STAY == 10.0
        assert WEIGHT_NULLSEC == 100.0

    def test_unsafe_mode_weights(self):
        """Unsafe mode weights are defined."""
        from aria_esi.services.navigation.weights import (
            WEIGHT_UNSAFE_NULLSEC,
            WEIGHT_UNSAFE_LOWSEC,
            WEIGHT_UNSAFE_HIGHSEC,
        )

        assert WEIGHT_UNSAFE_NULLSEC == 1.0
        assert WEIGHT_UNSAFE_LOWSEC == 2.0
        assert WEIGHT_UNSAFE_HIGHSEC == 10.0

    def test_avoid_weight_is_infinite(self):
        """Avoid weight is effectively infinite."""
        from aria_esi.services.navigation.weights import WEIGHT_AVOID

        assert WEIGHT_AVOID == float("inf")


# =============================================================================
# Avoid Weights Tests
# =============================================================================


class TestComputeAvoidWeights:
    """Test compute_avoid_weights function."""

    def test_no_avoidance(self, standard_universe):
        """Without avoidance, all weights are 1.0."""
        from aria_esi.services.navigation.weights import compute_avoid_weights

        weights = compute_avoid_weights(standard_universe, set())

        # All weights should be 1.0
        assert all(w == 1.0 for w in weights)

    def test_with_avoidance(self, standard_universe):
        """Avoided systems get infinite weight."""
        from aria_esi.services.navigation.weights import compute_avoid_weights, WEIGHT_AVOID

        # Avoid Perimeter (index 1)
        weights = compute_avoid_weights(standard_universe, {1})

        # Edges to Perimeter should have infinite weight
        g = standard_universe.graph
        for i, edge in enumerate(g.es):
            if edge.target == 1:
                assert weights[i] == WEIGHT_AVOID
            else:
                assert weights[i] == 1.0

    def test_multiple_avoidance(self, standard_universe):
        """Multiple avoided systems all get infinite weight."""
        from aria_esi.services.navigation.weights import compute_avoid_weights, WEIGHT_AVOID

        # Avoid Perimeter (1) and Maurasi (2)
        weights = compute_avoid_weights(standard_universe, {1, 2})

        g = standard_universe.graph
        for i, edge in enumerate(g.es):
            if edge.target in {1, 2}:
                assert weights[i] == WEIGHT_AVOID


# =============================================================================
# Safe Weights Tests
# =============================================================================


class TestComputeSafeWeights:
    """Test compute_safe_weights function."""

    def test_highsec_to_highsec_normal(self, standard_universe):
        """High-sec to high-sec has normal weight."""
        from aria_esi.services.navigation.weights import compute_safe_weights, WEIGHT_NORMAL

        weights = compute_safe_weights(standard_universe)

        # Jita (0.95) -> Perimeter (0.90) - both high-sec
        g = standard_universe.graph
        jita_idx = 0
        perimeter_idx = 1

        for i, edge in enumerate(g.es):
            if edge.source == jita_idx and edge.target == perimeter_idx:
                assert weights[i] == WEIGHT_NORMAL

    def test_highsec_to_lowsec_penalized(self, standard_universe):
        """High-sec to low-sec has entry penalty."""
        from aria_esi.services.navigation.weights import compute_safe_weights, WEIGHT_LOWSEC_ENTRY

        weights = compute_safe_weights(standard_universe)

        # Maurasi (0.65) -> Sivala (0.35) - high-sec to low-sec
        g = standard_universe.graph
        maurasi_idx = 2
        sivala_idx = 4

        for i, edge in enumerate(g.es):
            if edge.source == maurasi_idx and edge.target == sivala_idx:
                assert weights[i] == WEIGHT_LOWSEC_ENTRY

    def test_lowsec_to_nullsec_heavily_penalized(self, standard_universe):
        """Low-sec to null-sec has heavy penalty."""
        from aria_esi.services.navigation.weights import compute_safe_weights, WEIGHT_NULLSEC

        weights = compute_safe_weights(standard_universe)

        # Sivala (0.35) -> Ala (-0.2) - low-sec to null-sec
        g = standard_universe.graph
        sivala_idx = 4
        ala_idx = 5

        for i, edge in enumerate(g.es):
            if edge.source == sivala_idx and edge.target == ala_idx:
                assert weights[i] == WEIGHT_NULLSEC

    def test_safe_weights_with_avoidance(self, standard_universe):
        """Safe weights respects avoidance."""
        from aria_esi.services.navigation.weights import compute_safe_weights, WEIGHT_AVOID

        # Avoid Perimeter (1)
        weights = compute_safe_weights(standard_universe, avoid_systems={1})

        g = standard_universe.graph
        for i, edge in enumerate(g.es):
            if edge.target == 1:
                assert weights[i] == WEIGHT_AVOID


# =============================================================================
# Unsafe Weights Tests
# =============================================================================


class TestComputeUnsafeWeights:
    """Test compute_unsafe_weights function."""

    def test_nullsec_preferred(self, standard_universe):
        """Null-sec has lowest weight in unsafe mode."""
        from aria_esi.services.navigation.weights import (
            compute_unsafe_weights,
            WEIGHT_UNSAFE_NULLSEC,
        )

        weights = compute_unsafe_weights(standard_universe)

        # Any -> Ala (-0.2) - null-sec preferred
        g = standard_universe.graph
        ala_idx = 5

        for i, edge in enumerate(g.es):
            if edge.target == ala_idx:
                assert weights[i] == WEIGHT_UNSAFE_NULLSEC

    def test_lowsec_acceptable(self, standard_universe):
        """Low-sec has moderate weight in unsafe mode."""
        from aria_esi.services.navigation.weights import (
            compute_unsafe_weights,
            WEIGHT_UNSAFE_LOWSEC,
        )

        weights = compute_unsafe_weights(standard_universe)

        # Any -> Sivala (0.35) - low-sec acceptable
        g = standard_universe.graph
        sivala_idx = 4

        for i, edge in enumerate(g.es):
            if edge.target == sivala_idx:
                assert weights[i] == WEIGHT_UNSAFE_LOWSEC

    def test_highsec_avoided(self, standard_universe):
        """High-sec has high weight in unsafe mode."""
        from aria_esi.services.navigation.weights import (
            compute_unsafe_weights,
            WEIGHT_UNSAFE_HIGHSEC,
        )

        weights = compute_unsafe_weights(standard_universe)

        # Any -> Jita (0.95) - high-sec avoided
        g = standard_universe.graph
        jita_idx = 0

        for i, edge in enumerate(g.es):
            if edge.target == jita_idx:
                assert weights[i] == WEIGHT_UNSAFE_HIGHSEC

    def test_unsafe_weights_with_avoidance(self, standard_universe):
        """Unsafe weights respects avoidance."""
        from aria_esi.services.navigation.weights import compute_unsafe_weights, WEIGHT_AVOID

        # Avoid Sivala (4)
        weights = compute_unsafe_weights(standard_universe, avoid_systems={4})

        g = standard_universe.graph
        for i, edge in enumerate(g.es):
            if edge.target == 4:
                assert weights[i] == WEIGHT_AVOID
