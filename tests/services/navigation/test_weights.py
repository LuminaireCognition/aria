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
        """Avoided systems get infinite weight on all touching edges."""
        from aria_esi.services.navigation.weights import compute_avoid_weights, WEIGHT_AVOID

        # Avoid Perimeter (index 1)
        weights = compute_avoid_weights(standard_universe, {1})

        # Edges touching Perimeter (either endpoint) should have infinite weight
        g = standard_universe.graph
        for i, edge in enumerate(g.es):
            if edge.source == 1 or edge.target == 1:
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
            if edge.source in {1, 2} or edge.target in {1, 2}:
                assert weights[i] == WEIGHT_AVOID


# =============================================================================
# Safe Weights Tests
# =============================================================================


class TestComputeSafeWeights:
    """Test compute_safe_weights function."""

    def test_highsec_to_highsec_normal(self, standard_universe):
        """High-sec to high-sec edge has normal weight."""
        from aria_esi.services.navigation.weights import compute_safe_weights, WEIGHT_NORMAL

        weights = compute_safe_weights(standard_universe)

        # Jita (0.95) <-> Perimeter (0.90) - both high-sec
        g = standard_universe.graph
        jita_idx = 0
        perimeter_idx = 1

        for i, edge in enumerate(g.es):
            endpoints = {edge.source, edge.target}
            if endpoints == {jita_idx, perimeter_idx}:
                assert weights[i] == WEIGHT_NORMAL

    def test_highsec_lowsec_border_penalized(self, standard_universe):
        """Edge between high-sec and low-sec has entry penalty (symmetric)."""
        from aria_esi.services.navigation.weights import compute_safe_weights, WEIGHT_LOWSEC_ENTRY

        weights = compute_safe_weights(standard_universe)

        # Maurasi (0.65) <-> Sivala (0.35) - high-sec/low-sec border
        g = standard_universe.graph
        maurasi_idx = 2
        sivala_idx = 4

        for i, edge in enumerate(g.es):
            endpoints = {edge.source, edge.target}
            if endpoints == {maurasi_idx, sivala_idx}:
                assert weights[i] == WEIGHT_LOWSEC_ENTRY

    def test_lowsec_nullsec_border_heavily_penalized(self, standard_universe):
        """Edge between low-sec and null-sec has heavy penalty (symmetric)."""
        from aria_esi.services.navigation.weights import compute_safe_weights, WEIGHT_NULLSEC

        weights = compute_safe_weights(standard_universe)

        # Sivala (0.35) <-> Ala (-0.2) - low-sec/null-sec border
        g = standard_universe.graph
        sivala_idx = 4
        ala_idx = 5

        for i, edge in enumerate(g.es):
            endpoints = {edge.source, edge.target}
            if endpoints == {sivala_idx, ala_idx}:
                assert weights[i] == WEIGHT_NULLSEC

    def test_safe_weights_with_avoidance(self, standard_universe):
        """Safe weights respects avoidance on either endpoint."""
        from aria_esi.services.navigation.weights import compute_safe_weights, WEIGHT_AVOID

        # Avoid Perimeter (1)
        weights = compute_safe_weights(standard_universe, avoid_systems={1})

        g = standard_universe.graph
        for i, edge in enumerate(g.es):
            if edge.source == 1 or edge.target == 1:
                assert weights[i] == WEIGHT_AVOID


# =============================================================================
# Unsafe Weights Tests
# =============================================================================


class TestComputeUnsafeWeights:
    """Test compute_unsafe_weights function."""

    def test_nullsec_edge_preferred(self, standard_universe):
        """Edge touching null-sec has lowest weight in unsafe mode."""
        from aria_esi.services.navigation.weights import (
            compute_unsafe_weights,
            WEIGHT_UNSAFE_NULLSEC,
        )

        weights = compute_unsafe_weights(standard_universe)

        # Sivala (0.35) <-> Ala (-0.2) - touches null-sec, preferred
        g = standard_universe.graph
        sivala_idx = 4
        ala_idx = 5

        for i, edge in enumerate(g.es):
            endpoints = {edge.source, edge.target}
            if endpoints == {sivala_idx, ala_idx}:
                assert weights[i] == WEIGHT_UNSAFE_NULLSEC

    def test_lowsec_edge_acceptable(self, standard_universe):
        """Edge between high-sec and low-sec has moderate weight in unsafe mode."""
        from aria_esi.services.navigation.weights import (
            compute_unsafe_weights,
            WEIGHT_UNSAFE_LOWSEC,
        )

        weights = compute_unsafe_weights(standard_universe)

        # Maurasi (0.65) <-> Sivala (0.35) - worst sec is 0.35 (low-sec)
        g = standard_universe.graph
        maurasi_idx = 2
        sivala_idx = 4

        for i, edge in enumerate(g.es):
            endpoints = {edge.source, edge.target}
            if endpoints == {maurasi_idx, sivala_idx}:
                assert weights[i] == WEIGHT_UNSAFE_LOWSEC

    def test_highsec_edge_avoided(self, standard_universe):
        """Edge between two high-sec systems has high weight in unsafe mode."""
        from aria_esi.services.navigation.weights import (
            compute_unsafe_weights,
            WEIGHT_UNSAFE_HIGHSEC,
        )

        weights = compute_unsafe_weights(standard_universe)

        # Jita (0.95) <-> Perimeter (0.90) - both high-sec, avoided
        g = standard_universe.graph
        jita_idx = 0
        perimeter_idx = 1

        for i, edge in enumerate(g.es):
            endpoints = {edge.source, edge.target}
            if endpoints == {jita_idx, perimeter_idx}:
                assert weights[i] == WEIGHT_UNSAFE_HIGHSEC

    def test_unsafe_weights_with_avoidance(self, standard_universe):
        """Unsafe weights respects avoidance on either endpoint."""
        from aria_esi.services.navigation.weights import compute_unsafe_weights, WEIGHT_AVOID

        # Avoid Sivala (4)
        weights = compute_unsafe_weights(standard_universe, avoid_systems={4})

        g = standard_universe.graph
        for i, edge in enumerate(g.es):
            if edge.source == 4 or edge.target == 4:
                assert weights[i] == WEIGHT_AVOID


# =============================================================================
# Undirected Graph Symmetry Regression Tests
# =============================================================================


class TestUndirectedSymmetry:
    """
    Regression tests ensuring weight functions produce correct results
    regardless of igraph's arbitrary source/target assignment for
    undirected edges.
    """

    def test_safe_border_weight_deterministic(self):
        """Border edge weight is the same regardless of igraph edge direction."""
        from aria_esi.services.navigation.weights import (
            compute_safe_weights,
            WEIGHT_LOWSEC_ENTRY,
        )

        # Create two universes with the same edge but reversed vertex order
        # to force igraph to assign different source/target
        systems = [
            {"name": "HighSec", "id": 1, "sec": 0.7, "const": 1, "region": 1},
            {"name": "LowSec", "id": 2, "sec": 0.3, "const": 1, "region": 1},
        ]
        edges_fwd = [(0, 1)]  # igraph stores HighSec→LowSec
        edges_rev = [(1, 0)]  # igraph stores LowSec→HighSec

        u_fwd = create_mock_universe(systems, edges_fwd)
        u_rev = create_mock_universe(systems, edges_rev)

        w_fwd = compute_safe_weights(u_fwd)
        w_rev = compute_safe_weights(u_rev)

        assert w_fwd[0] == WEIGHT_LOWSEC_ENTRY
        assert w_rev[0] == WEIGHT_LOWSEC_ENTRY
        assert w_fwd[0] == w_rev[0]

    def test_avoid_blocks_regardless_of_direction(self):
        """Avoided system is blocked whether it's edge.source or edge.target."""
        from aria_esi.services.navigation.weights import (
            compute_avoid_weights,
            WEIGHT_AVOID,
        )

        systems = [
            {"name": "Safe", "id": 1, "sec": 0.9, "const": 1, "region": 1},
            {"name": "Danger", "id": 2, "sec": 0.3, "const": 1, "region": 1},
        ]
        edges_fwd = [(0, 1)]
        edges_rev = [(1, 0)]

        u_fwd = create_mock_universe(systems, edges_fwd)
        u_rev = create_mock_universe(systems, edges_rev)

        # Avoid "Danger" (index 1)
        w_fwd = compute_avoid_weights(u_fwd, {1})
        w_rev = compute_avoid_weights(u_rev, {1})

        assert w_fwd[0] == WEIGHT_AVOID
        assert w_rev[0] == WEIGHT_AVOID

    def test_unsafe_border_weight_deterministic(self):
        """Unsafe mode uses most dangerous endpoint regardless of direction."""
        from aria_esi.services.navigation.weights import (
            compute_unsafe_weights,
            WEIGHT_UNSAFE_LOWSEC,
        )

        systems = [
            {"name": "HighSec", "id": 1, "sec": 0.7, "const": 1, "region": 1},
            {"name": "LowSec", "id": 2, "sec": 0.3, "const": 1, "region": 1},
        ]
        edges_fwd = [(0, 1)]
        edges_rev = [(1, 0)]

        u_fwd = create_mock_universe(systems, edges_fwd)
        u_rev = create_mock_universe(systems, edges_rev)

        w_fwd = compute_unsafe_weights(u_fwd)
        w_rev = compute_unsafe_weights(u_rev)

        assert w_fwd[0] == WEIGHT_UNSAFE_LOWSEC
        assert w_rev[0] == WEIGHT_UNSAFE_LOWSEC

    def test_territory_preference_symmetric(self):
        """Territory preference applies when neither endpoint is in territory."""
        from aria_esi.services.navigation.weights import (
            apply_territory_preference,
            WEIGHT_TERRITORY_PENALTY,
        )

        systems = [
            {"name": "Home", "id": 1, "sec": 0.9, "const": 1, "region": 1},
            {"name": "Away", "id": 2, "sec": 0.8, "const": 1, "region": 1},
            {"name": "Also Away", "id": 3, "sec": 0.7, "const": 1, "region": 1},
        ]
        edges = [(0, 1), (1, 2)]
        universe = create_mock_universe(systems, edges)

        base_weights = [1.0, 1.0]
        # Home (0) is in preferred territory
        result = apply_territory_preference(base_weights, universe, {0})

        # Edge Home<->Away: one endpoint (Home) is in territory — no penalty
        # Edge Away<->Also Away: neither endpoint in territory — penalized
        g = universe.graph
        for i, edge in enumerate(g.es):
            endpoints = {edge.source, edge.target}
            if 0 in endpoints:
                assert result[i] == 1.0
            else:
                assert result[i] == 1.0 * WEIGHT_TERRITORY_PENALTY
