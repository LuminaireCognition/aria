"""
Tests for Pattern Escalation Layer.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from aria_esi.services.redisq.interest.layers import (
    ESCALATION_TTL_SECONDS,
    GATECAMP_MULTIPLIER,
    PatternConfig,
    PatternLayer,
)
from aria_esi.services.redisq.interest.models import PatternEscalation

# =============================================================================
# Configuration Tests
# =============================================================================


class TestPatternConfig:
    """Tests for PatternConfig."""

    def test_from_dict_parses_all_fields(self) -> None:
        """Config parses all fields from dict."""
        data = {
            "gatecamp_detection": True,
            "spike_detection": False,
            "gatecamp_multiplier": 1.5,
            "spike_multiplier": 1.3,
            "spike_threshold": 3.0,
            "escalation_ttl_seconds": 300,
        }

        config = PatternConfig.from_dict(data)

        assert config.gatecamp_detection is True
        assert config.spike_detection is False
        assert config.gatecamp_multiplier == 1.5
        assert config.spike_multiplier == 1.3
        assert config.spike_threshold == 3.0
        assert config.escalation_ttl_seconds == 300

    def test_default_config(self) -> None:
        """Default config has sensible values."""
        config = PatternConfig.from_dict(None)

        assert config.gatecamp_detection is True
        assert config.spike_detection is True
        assert config.gatecamp_multiplier == GATECAMP_MULTIPLIER
        assert config.spike_threshold == 2.0
        assert config.escalation_ttl_seconds == ESCALATION_TTL_SECONDS


# =============================================================================
# Scoring Tests
# =============================================================================


class TestPatternLayerScoring:
    """Tests for pattern layer scoring."""

    def test_no_escalation_returns_1_0(self) -> None:
        """System without escalation returns 1.0 multiplier."""
        layer = PatternLayer.from_config(PatternConfig())

        score = layer.score_system(30000142)

        assert score.score == 1.0
        assert score.reason is None

    def test_manual_escalation_returns_multiplier(self) -> None:
        """Manually set escalation returns configured multiplier."""
        layer = PatternLayer.from_config(PatternConfig())
        layer.set_escalation(30000142, 1.5, "Test escalation")

        score = layer.score_system(30000142)

        assert score.score == 1.5
        assert "Test escalation" in score.reason


# =============================================================================
# Escalation Management Tests
# =============================================================================


class TestEscalationManagement:
    """Tests for managing escalations."""

    def test_set_and_get_escalation(self) -> None:
        """Can set and retrieve escalation."""
        layer = PatternLayer.from_config(PatternConfig())

        layer.set_escalation(30000142, 1.5, "Gatecamp forming")

        escalation = layer.get_escalation(30000142)
        assert escalation.multiplier == 1.5
        assert "Gatecamp" in escalation.reason

    def test_escalation_expires_after_ttl(self) -> None:
        """Escalation expires after TTL."""
        config = PatternConfig(escalation_ttl_seconds=1)  # 1 second TTL
        layer = PatternLayer.from_config(config)

        layer.set_escalation(30000142, 1.5, "Short escalation", ttl_seconds=1)

        # Immediately after setting
        assert layer.get_escalation(30000142).multiplier == 1.5

        # After TTL
        time.sleep(1.1)
        assert layer.get_escalation(30000142).multiplier == 1.0

    def test_clear_escalation(self) -> None:
        """Can clear specific escalation."""
        layer = PatternLayer.from_config(PatternConfig())

        layer.set_escalation(30000142, 1.5, "Test")
        assert layer.get_escalation(30000142).multiplier == 1.5

        layer.clear_escalation(30000142)
        assert layer.get_escalation(30000142).multiplier == 1.0

    def test_clear_expired_escalations(self) -> None:
        """Can clear all expired escalations."""
        layer = PatternLayer.from_config(PatternConfig())

        # Set some escalations with short TTL
        layer.set_escalation(30000142, 1.5, "Test", ttl_seconds=0)
        layer.set_escalation(30000143, 1.5, "Test", ttl_seconds=0)
        layer.set_escalation(30000144, 1.5, "Test", ttl_seconds=9999)

        # Clear expired
        time.sleep(0.1)
        cleared = layer.clear_expired_escalations()

        assert cleared == 2  # Two expired
        assert layer.active_escalation_count == 1  # One still active

    def test_get_all_escalations(self) -> None:
        """Can get all active escalations."""
        layer = PatternLayer.from_config(PatternConfig())

        layer.set_escalation(30000142, 1.5, "Test 1")
        layer.set_escalation(30000143, 1.3, "Test 2")

        all_esc = layer.get_all_escalations()

        assert 30000142 in all_esc
        assert 30000143 in all_esc
        assert all_esc[30000142].multiplier == 1.5


# =============================================================================
# ThreatCache Integration Tests
# =============================================================================


class TestThreatCacheIntegration:
    """Tests for ThreatCache integration."""

    def test_gatecamp_detection_with_cache(self) -> None:
        """Detects gatecamp from ThreatCache."""
        # Mock ThreatCache
        mock_cache = MagicMock()
        mock_cache.get_gatecamp_status.return_value = MagicMock(
            confidence="high",
            kill_count=5,
        )

        layer = PatternLayer.from_config(
            PatternConfig(gatecamp_multiplier=1.5),
            threat_cache=mock_cache,
        )

        # Should detect gatecamp
        score = layer.score_system(30000142)

        assert score.score == 1.5
        assert "gatecamp" in score.reason.lower()
        mock_cache.get_gatecamp_status.assert_called_with(30000142)

    def test_no_gatecamp_returns_1_0(self) -> None:
        """No gatecamp detected returns 1.0."""
        mock_cache = MagicMock()
        mock_cache.get_gatecamp_status.return_value = None
        mock_cache.detect_activity_spike.return_value = None

        layer = PatternLayer.from_config(PatternConfig(), threat_cache=mock_cache)

        score = layer.score_system(30000142)

        assert score.score == 1.0

    def test_gatecamp_detection_disabled(self) -> None:
        """Gatecamp detection can be disabled."""
        mock_cache = MagicMock()
        mock_cache.get_gatecamp_status.return_value = MagicMock(confidence="high")
        mock_cache.detect_activity_spike.return_value = None

        config = PatternConfig(gatecamp_detection=False)
        layer = PatternLayer.from_config(config, threat_cache=mock_cache)

        score = layer.score_system(30000142)

        # Should not check cache
        mock_cache.get_gatecamp_status.assert_not_called()
        assert score.score == 1.0


# =============================================================================
# Spike Detection Tests
# =============================================================================


class TestSpikeDetection:
    """Tests for activity spike detection."""

    def test_spike_detection_when_above_threshold(self) -> None:
        """Detects spike when activity exceeds threshold."""
        mock_cache = MagicMock()
        mock_cache.get_gatecamp_status.return_value = None
        # Spike detected: 10 kills/h vs 2.0 baseline (5x normal)
        mock_cache.detect_activity_spike.return_value = (True, 10.0, 2.0)

        config = PatternConfig(spike_detection=True, spike_multiplier=1.3)
        layer = PatternLayer.from_config(config, threat_cache=mock_cache)

        score = layer.score_system(30000142)

        assert score.score == 1.3
        assert "spike" in score.reason.lower()
        assert "10/h" in score.reason
        assert "2.0 baseline" in score.reason
        mock_cache.detect_activity_spike.assert_called_once()

    def test_no_spike_when_below_threshold(self) -> None:
        """No escalation when activity is below threshold."""
        mock_cache = MagicMock()
        mock_cache.get_gatecamp_status.return_value = None
        # No spike: 3 kills/h vs 2.0 baseline (1.5x normal, below 2.0 threshold)
        mock_cache.detect_activity_spike.return_value = (False, 3.0, 2.0)

        config = PatternConfig(spike_detection=True)
        layer = PatternLayer.from_config(config, threat_cache=mock_cache)

        score = layer.score_system(30000142)

        assert score.score == 1.0
        assert score.reason is None

    def test_spike_detection_with_insufficient_data_returns_no_escalation(self) -> None:
        """No escalation when insufficient historical data."""
        mock_cache = MagicMock()
        mock_cache.get_gatecamp_status.return_value = None
        # Insufficient data returns None
        mock_cache.detect_activity_spike.return_value = None

        config = PatternConfig(spike_detection=True)
        layer = PatternLayer.from_config(config, threat_cache=mock_cache)

        score = layer.score_system(30000142)

        assert score.score == 1.0
        assert score.reason is None

    def test_spike_detection_disabled(self) -> None:
        """Spike detection can be disabled."""
        mock_cache = MagicMock()
        mock_cache.get_gatecamp_status.return_value = None

        config = PatternConfig(spike_detection=False)
        layer = PatternLayer.from_config(config, threat_cache=mock_cache)

        score = layer.score_system(30000142)

        # Should not check for spike
        mock_cache.detect_activity_spike.assert_not_called()
        assert score.score == 1.0

    def test_gatecamp_takes_precedence_over_spike(self) -> None:
        """Gatecamp escalation takes priority over spike."""
        mock_cache = MagicMock()
        # Both gatecamp and spike detected
        mock_cache.get_gatecamp_status.return_value = MagicMock(confidence="high")
        mock_cache.detect_activity_spike.return_value = (True, 10.0, 2.0)

        config = PatternConfig(
            gatecamp_detection=True,
            spike_detection=True,
            gatecamp_multiplier=1.5,
            spike_multiplier=1.3,
        )
        layer = PatternLayer.from_config(config, threat_cache=mock_cache)

        score = layer.score_system(30000142)

        # Gatecamp should win (1.5 > 1.3)
        assert score.score == 1.5
        assert "gatecamp" in score.reason.lower()
        # Spike detection should not even be called
        mock_cache.detect_activity_spike.assert_not_called()

    def test_spike_threshold_config_parameter(self) -> None:
        """Spike threshold is passed to ThreatCache."""
        mock_cache = MagicMock()
        mock_cache.get_gatecamp_status.return_value = None
        mock_cache.detect_activity_spike.return_value = None

        config = PatternConfig(spike_detection=True, spike_threshold=3.5)
        layer = PatternLayer.from_config(config, threat_cache=mock_cache)

        layer.score_system(30000142)

        # Verify threshold was passed
        mock_cache.detect_activity_spike.assert_called_with(30000142, spike_threshold=3.5)


# =============================================================================
# PatternEscalation Model Tests
# =============================================================================


class TestPatternEscalation:
    """Tests for PatternEscalation dataclass."""

    def test_is_expired_with_no_expiry(self) -> None:
        """Escalation without expiry never expires."""
        esc = PatternEscalation(multiplier=1.5, expires_at=None)

        assert esc.is_expired() is False

    def test_is_expired_checks_time(self) -> None:
        """Escalation checks against current time."""
        past_time = time.time() - 100
        future_time = time.time() + 100

        expired = PatternEscalation(multiplier=1.5, expires_at=past_time)
        not_expired = PatternEscalation(multiplier=1.5, expires_at=future_time)

        assert expired.is_expired() is True
        assert not_expired.is_expired() is False

    def test_is_expired_with_provided_time(self) -> None:
        """Can check expiry against provided time."""
        esc = PatternEscalation(multiplier=1.5, expires_at=1000)

        assert esc.is_expired(now=500) is False  # Before expiry
        assert esc.is_expired(now=1500) is True  # After expiry


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for serialization."""

    def test_to_dict_includes_config(self) -> None:
        """to_dict includes configuration."""
        config = PatternConfig(gatecamp_multiplier=1.5)
        layer = PatternLayer.from_config(config)

        data = layer.to_dict()

        assert data["config"]["gatecamp_multiplier"] == 1.5

    def test_from_dict_restores_config(self) -> None:
        """from_dict restores configuration."""
        config = PatternConfig(gatecamp_multiplier=1.8)
        layer = PatternLayer.from_config(config)

        data = layer.to_dict()
        restored = PatternLayer.from_dict(data)

        assert restored.config.gatecamp_multiplier == 1.8


# =============================================================================
# Calculator Integration Tests
# =============================================================================


class TestCalculatorIntegration:
    """Tests for integration with InterestCalculator."""

    def test_pattern_layer_as_escalation(self) -> None:
        """Pattern layer works as escalation in calculator."""
        from aria_esi.services.redisq.interest import InterestCalculator

        from .conftest import MockGeographicLayer

        geo_layer = MockGeographicLayer(interest_map={30000142: 0.6})

        pattern_layer = PatternLayer.from_config(PatternConfig())
        pattern_layer.set_escalation(30000142, 1.5, "Gatecamp detected")

        calculator = InterestCalculator(layers=[geo_layer])
        calculator.set_pattern_layer(pattern_layer)

        score = calculator.calculate_system_interest(30000142)

        # 0.6 * 1.5 = 0.9
        assert score.interest == pytest.approx(0.9)
        assert score.base_interest == pytest.approx(0.6)
        assert score.escalation is not None
        assert score.escalation.multiplier == 1.5
