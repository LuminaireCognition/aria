"""
Tests for arbitrage_freshness module.

Tests freshness classification, confidence scoring, and volume utilities.
"""

import time
from unittest.mock import patch

from aria_esi.services.arbitrage_freshness import (
    FRESH_THRESHOLD,
    RECENT_THRESHOLD,
    SCOPE_FRESH_THRESHOLD,
    SCOPE_RECENT_THRESHOLD,
    get_combined_freshness,
    get_confidence,
    get_effective_volume,
    get_freshness,
    get_scope_freshness,
)


class TestGetFreshness:
    """Tests for get_freshness function (hub data thresholds)."""

    def test_fresh_data(self):
        """Test that recent data is classified as fresh."""
        # Data from 2 minutes ago
        timestamp = int(time.time()) - 120
        assert get_freshness(timestamp) == "fresh"

    def test_recent_data(self):
        """Test that moderately old data is classified as recent."""
        # Data from 10 minutes ago
        timestamp = int(time.time()) - 600
        assert get_freshness(timestamp) == "recent"

    def test_stale_data(self):
        """Test that old data is classified as stale."""
        # Data from 1 hour ago
        timestamp = int(time.time()) - 3600
        assert get_freshness(timestamp) == "stale"

    def test_boundary_fresh_to_recent(self):
        """Test boundary between fresh and recent (5 minutes)."""
        now = time.time()
        with patch("aria_esi.services.arbitrage_freshness.time.time", return_value=now):
            # Just under 5 minutes
            assert get_freshness(int(now - FRESH_THRESHOLD + 1)) == "fresh"
            # Exactly at 5 minutes
            assert get_freshness(int(now - FRESH_THRESHOLD)) == "recent"

    def test_boundary_recent_to_stale(self):
        """Test boundary between recent and stale (30 minutes)."""
        now = time.time()
        with patch("aria_esi.services.arbitrage_freshness.time.time", return_value=now):
            # Just under 30 minutes
            assert get_freshness(int(now - RECENT_THRESHOLD + 1)) == "recent"
            # Exactly at 30 minutes
            assert get_freshness(int(now - RECENT_THRESHOLD)) == "stale"


class TestGetScopeFreshness:
    """Tests for get_scope_freshness function (more lenient thresholds)."""

    def test_fresh_scope_data(self):
        """Test that recent scope data is classified as fresh."""
        # Data from 5 minutes ago (within 10 minute threshold)
        timestamp = int(time.time()) - 300
        assert get_scope_freshness(timestamp) == "fresh"

    def test_recent_scope_data(self):
        """Test that moderately old scope data is classified as recent."""
        # Data from 30 minutes ago (within 60 minute threshold)
        timestamp = int(time.time()) - 1800
        assert get_scope_freshness(timestamp) == "recent"

    def test_stale_scope_data(self):
        """Test that old scope data is classified as stale."""
        # Data from 2 hours ago
        timestamp = int(time.time()) - 7200
        assert get_scope_freshness(timestamp) == "stale"

    def test_scope_thresholds_more_lenient(self):
        """Test that scope thresholds are more lenient than hub thresholds."""
        assert SCOPE_FRESH_THRESHOLD > FRESH_THRESHOLD
        assert SCOPE_RECENT_THRESHOLD > RECENT_THRESHOLD

    def test_boundary_fresh_to_recent(self):
        """Test boundary between fresh and recent for scopes (10 minutes)."""
        now = time.time()
        with patch("aria_esi.services.arbitrage_freshness.time.time", return_value=now):
            # Just under 10 minutes
            assert get_scope_freshness(int(now - SCOPE_FRESH_THRESHOLD + 1)) == "fresh"
            # Exactly at 10 minutes
            assert get_scope_freshness(int(now - SCOPE_FRESH_THRESHOLD)) == "recent"


class TestGetConfidence:
    """Tests for get_confidence function."""

    def test_high_confidence_both_fresh(self):
        """Test high confidence when both sides are fresh."""
        assert get_confidence("fresh", "fresh") == "high"

    def test_medium_confidence_one_recent(self):
        """Test medium confidence when at least one side is recent."""
        assert get_confidence("fresh", "recent") == "medium"
        assert get_confidence("recent", "fresh") == "medium"
        assert get_confidence("recent", "recent") == "medium"

    def test_low_confidence_any_stale(self):
        """Test low confidence when any side is stale."""
        assert get_confidence("stale", "fresh") == "low"
        assert get_confidence("fresh", "stale") == "low"
        assert get_confidence("stale", "recent") == "low"
        assert get_confidence("recent", "stale") == "low"
        assert get_confidence("stale", "stale") == "low"


class TestGetCombinedFreshness:
    """Tests for get_combined_freshness function."""

    def test_combined_fresh(self):
        """Test combined freshness when both sides are fresh."""
        assert get_combined_freshness("fresh", "fresh") == "fresh"

    def test_combined_recent_when_one_recent(self):
        """Test combined freshness is recent when one side is recent."""
        assert get_combined_freshness("fresh", "recent") == "recent"
        assert get_combined_freshness("recent", "fresh") == "recent"
        assert get_combined_freshness("recent", "recent") == "recent"

    def test_combined_stale_when_any_stale(self):
        """Test combined freshness is stale when any side is stale."""
        assert get_combined_freshness("stale", "fresh") == "stale"
        assert get_combined_freshness("fresh", "stale") == "stale"
        assert get_combined_freshness("stale", "recent") == "stale"
        assert get_combined_freshness("recent", "stale") == "stale"
        assert get_combined_freshness("stale", "stale") == "stale"


class TestGetEffectiveVolume:
    """Tests for get_effective_volume function."""

    def test_prefers_packaged_volume(self):
        """Test that packaged volume is preferred over regular volume."""
        volume, source = get_effective_volume(100.0, 10.0)
        assert volume == 10.0
        assert source == "sde_packaged"

    def test_falls_back_to_volume(self):
        """Test fallback to regular volume when packaged is not available."""
        volume, source = get_effective_volume(100.0, None)
        assert volume == 100.0
        assert source == "sde_volume"

        volume, source = get_effective_volume(100.0, 0.0)
        assert volume == 100.0
        assert source == "sde_volume"

    def test_falls_back_to_default(self):
        """Test fallback to default when neither volume is available."""
        from aria_esi.models.market import DEFAULT_VOLUME_M3

        volume, source = get_effective_volume(None, None)
        assert volume == DEFAULT_VOLUME_M3
        assert source == "fallback"

        volume, source = get_effective_volume(0.0, 0.0)
        assert volume == DEFAULT_VOLUME_M3
        assert source == "fallback"

    def test_zero_volumes_fallback(self):
        """Test that zero volumes trigger fallback."""
        from aria_esi.models.market import DEFAULT_VOLUME_M3

        volume, source = get_effective_volume(0.0, 0.0)
        assert volume == DEFAULT_VOLUME_M3
        assert source == "fallback"

    def test_negative_volumes_treated_as_invalid(self):
        """Test that negative volumes are treated as invalid."""
        from aria_esi.models.market import DEFAULT_VOLUME_M3

        # Negative packaged volume should be skipped
        volume, source = get_effective_volume(100.0, -5.0)
        assert volume == 100.0
        assert source == "sde_volume"

        # Negative both should fallback
        volume, source = get_effective_volume(-5.0, -5.0)
        assert volume == DEFAULT_VOLUME_M3
        assert source == "fallback"


class TestConstants:
    """Tests for module constants."""

    def test_hub_thresholds(self):
        """Test hub data threshold constants."""
        assert FRESH_THRESHOLD == 300  # 5 minutes
        assert RECENT_THRESHOLD == 1800  # 30 minutes

    def test_scope_thresholds(self):
        """Test scope data threshold constants."""
        assert SCOPE_FRESH_THRESHOLD == 600  # 10 minutes
        assert SCOPE_RECENT_THRESHOLD == 3600  # 1 hour
