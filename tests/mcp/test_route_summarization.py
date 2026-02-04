"""
Tests for route summarization functionality.

Routes >20 jumps are summarized to show first 5 + summary + last 5 systems
per CONTEXT_POLICY.md requirements.
"""

from __future__ import annotations

from aria_esi.mcp.context import summarize_route
from aria_esi.mcp.context_policy import UNIVERSE


def _make_system(name: str, security: float) -> dict:
    """Helper to create a mock system dict."""
    return {"name": name, "security": security}


def _make_route(count: int, security_pattern: str = "highsec") -> list[dict]:
    """
    Create a mock route with specified number of systems.

    Args:
        count: Number of systems in route
        security_pattern: 'highsec', 'lowsec', 'nullsec', or 'mixed'

    Returns:
        List of system dicts
    """
    systems = []
    for i in range(count):
        if security_pattern == "highsec":
            sec = 0.8
        elif security_pattern == "lowsec":
            sec = 0.3
        elif security_pattern == "nullsec":
            sec = -0.5
        elif security_pattern == "mixed":
            # Pattern: highsec -> lowsec -> nullsec -> lowsec -> highsec
            progress = i / max(count - 1, 1)
            if progress < 0.25:
                sec = 0.8 - progress * 2
            elif progress < 0.5:
                sec = 0.3 - (progress - 0.25) * 2
            elif progress < 0.75:
                sec = -0.2 + (progress - 0.5) * 2
            else:
                sec = 0.3 + (progress - 0.75) * 2
        else:
            sec = 0.5

        systems.append(_make_system(f"System{i}", round(sec, 2)))

    return systems


class TestShortRouteNoSummarization:
    """Short routes should not be summarized."""

    def test_route_under_threshold(self):
        """Route with 15 jumps should remain unchanged."""
        systems = _make_route(15)
        data = {"systems": systems, "jumps": 14}

        result = summarize_route(data, threshold=20)

        assert len(result["systems"]) == 15
        assert result["_meta"]["count"] == 15
        assert "summarized" not in result["_meta"]

    def test_route_at_threshold_not_summarized(self):
        """Route exactly at threshold (20) should NOT be summarized."""
        systems = _make_route(20)
        data = {"systems": systems, "jumps": 19}

        result = summarize_route(data, threshold=20)

        assert len(result["systems"]) == 20
        assert result["_meta"]["count"] == 20
        assert "summarized" not in result["_meta"]

    def test_empty_route(self):
        """Empty route should be handled gracefully."""
        data = {"systems": [], "jumps": 0}

        result = summarize_route(data)

        assert result["systems"] == []
        assert result["_meta"]["count"] == 0

    def test_single_system(self):
        """Single system route should not be summarized."""
        data = {"systems": [_make_system("Jita", 0.95)], "jumps": 0}

        result = summarize_route(data)

        assert len(result["systems"]) == 1
        assert result["_meta"]["count"] == 1


class TestLongRouteSummarization:
    """Long routes should be summarized with head + summary + tail."""

    def test_long_route_summarized(self):
        """45-jump route becomes 5 + summary + 5 = 11 entries."""
        systems = _make_route(45)
        data = {"systems": systems, "jumps": 44}

        result = summarize_route(data, threshold=20, head=5, tail=5)

        # 5 head + 1 summary + 5 tail = 11
        assert len(result["systems"]) == 11
        assert result["_meta"]["count"] == 11
        assert result["_meta"]["summarized"] is True
        assert result["_meta"]["original_count"] == 45

    def test_just_over_threshold(self):
        """Route just over threshold (21) should be summarized."""
        systems = _make_route(21)
        data = {"systems": systems, "jumps": 20}

        result = summarize_route(data, threshold=20, head=5, tail=5)

        # 21 systems: 5 head + 1 summary (11 skipped) + 5 tail = 11
        assert len(result["systems"]) == 11
        assert result["_meta"]["summarized"] is True

        # Check summary is in correct position
        summary = result["systems"][5]
        assert summary["_summary"] is True
        assert summary["skipped_count"] == 11

    def test_head_systems_preserved(self):
        """First 5 systems should be preserved exactly."""
        systems = _make_route(30)
        data = {"systems": systems, "jumps": 29}

        result = summarize_route(data, threshold=20, head=5, tail=5)

        # Verify first 5 match original
        for i in range(5):
            assert result["systems"][i]["name"] == f"System{i}"

    def test_tail_systems_preserved(self):
        """Last 5 systems should be preserved exactly."""
        systems = _make_route(30)
        data = {"systems": systems, "jumps": 29}

        result = summarize_route(data, threshold=20, head=5, tail=5)

        # Verify last 5 match original
        for i in range(5):
            original_idx = 30 - 5 + i
            result_idx = 11 - 5 + i  # 11 = 5 + 1 + 5
            assert result["systems"][result_idx]["name"] == f"System{original_idx}"


class TestSummarySecurityBreakdown:
    """Summary should contain accurate security breakdown."""

    def test_highsec_only_route(self):
        """All-highsec route should show all in highsec."""
        systems = _make_route(30, security_pattern="highsec")
        data = {"systems": systems}

        result = summarize_route(data, threshold=20, head=5, tail=5)

        summary = result["systems"][5]
        assert summary["_summary"] is True
        assert summary["security_breakdown"]["highsec"] == 20  # 30 - 5 - 5 = 20 skipped
        assert summary["security_breakdown"]["lowsec"] == 0
        assert summary["security_breakdown"]["nullsec"] == 0

    def test_lowsec_only_route(self):
        """All-lowsec route should show all in lowsec."""
        systems = _make_route(30, security_pattern="lowsec")
        data = {"systems": systems}

        result = summarize_route(data, threshold=20, head=5, tail=5)

        summary = result["systems"][5]
        assert summary["security_breakdown"]["highsec"] == 0
        assert summary["security_breakdown"]["lowsec"] == 20
        assert summary["security_breakdown"]["nullsec"] == 0

    def test_nullsec_only_route(self):
        """All-nullsec route should show all in nullsec."""
        systems = _make_route(30, security_pattern="nullsec")
        data = {"systems": systems}

        result = summarize_route(data, threshold=20, head=5, tail=5)

        summary = result["systems"][5]
        assert summary["security_breakdown"]["highsec"] == 0
        assert summary["security_breakdown"]["lowsec"] == 0
        assert summary["security_breakdown"]["nullsec"] == 20

    def test_mixed_security_route(self):
        """Mixed security route should break down correctly."""
        # Create specific mix: 10 highsec, 10 lowsec, 10 nullsec
        systems = []
        for i in range(10):
            systems.append(_make_system(f"High{i}", 0.8))
        for i in range(10):
            systems.append(_make_system(f"Low{i}", 0.3))
        for i in range(10):
            systems.append(_make_system(f"Null{i}", -0.3))

        data = {"systems": systems}

        result = summarize_route(data, threshold=20, head=5, tail=5)

        summary = result["systems"][5]
        # Skipped systems: 30 - 5 - 5 = 20
        # First 5 are highsec (head), last 5 are nullsec (tail)
        # Middle 20: 5 highsec + 10 lowsec + 5 nullsec
        assert summary["security_breakdown"]["highsec"] == 5
        assert summary["security_breakdown"]["lowsec"] == 10
        assert summary["security_breakdown"]["nullsec"] == 5


class TestSummaryLowestSecurity:
    """Summary should track lowest security system."""

    def test_lowest_security_tracked(self):
        """Should track the lowest security system in skipped section."""
        systems = [
            _make_system("Start", 0.9),
            _make_system("High1", 0.8),
            _make_system("High2", 0.7),
            _make_system("High3", 0.6),
            _make_system("High4", 0.5),
            # --- head ends here ---
            _make_system("Mid1", 0.4),
            _make_system("Mid2", 0.3),
            _make_system("Danger", -0.5),  # Lowest!
            _make_system("Mid3", 0.2),
            _make_system("Mid4", 0.1),
            # ... more middle systems
        ]
        # Add more to make it 25 total
        for i in range(15):
            systems.append(_make_system(f"End{i}", 0.5 + i * 0.02))

        data = {"systems": systems}

        result = summarize_route(data, threshold=20, head=5, tail=5)

        summary = result["systems"][5]
        assert summary["lowest_security"] == -0.5
        assert summary["lowest_security_system"] == "Danger"

    def test_lowest_security_tie(self):
        """When multiple systems have same lowest sec, first one is reported."""
        systems = []
        for i in range(5):
            systems.append(_make_system(f"Head{i}", 0.8))
        systems.append(_make_system("FirstLow", 0.1))
        systems.append(_make_system("SecondLow", 0.1))
        for i in range(18):
            systems.append(_make_system(f"Mid{i}", 0.5))

        data = {"systems": systems}

        result = summarize_route(data, threshold=20, head=5, tail=5)

        summary = result["systems"][5]
        assert summary["lowest_security"] == 0.1
        assert summary["lowest_security_system"] == "FirstLow"


class TestMetaSummarizedFlag:
    """Verify _meta.summarized flag is set correctly."""

    def test_summarized_flag_true(self):
        """Should set summarized=True when route is summarized."""
        systems = _make_route(30)
        data = {"systems": systems}

        result = summarize_route(data, threshold=20)

        assert result["_meta"]["summarized"] is True

    def test_summarized_flag_absent_when_not_summarized(self):
        """Should NOT set summarized flag when route is short."""
        systems = _make_route(15)
        data = {"systems": systems}

        result = summarize_route(data, threshold=20)

        assert "summarized" not in result["_meta"]

    def test_original_count_preserved(self):
        """Should preserve original count in metadata."""
        systems = _make_route(45)
        data = {"systems": systems}

        result = summarize_route(data, threshold=20)

        assert result["_meta"]["original_count"] == 45


class TestCustomParameters:
    """Test custom threshold, head, and tail parameters."""

    def test_custom_threshold(self):
        """Should respect custom threshold."""
        systems = _make_route(15)
        data = {"systems": systems}

        # With threshold=10, 15 systems should be summarized
        result = summarize_route(data, threshold=10, head=3, tail=3)

        assert result["_meta"]["summarized"] is True
        assert len(result["systems"]) == 7  # 3 + 1 + 3

    def test_custom_head_tail(self):
        """Should respect custom head/tail counts."""
        systems = _make_route(50)
        data = {"systems": systems}

        result = summarize_route(data, threshold=20, head=10, tail=10)

        # 10 + 1 + 10 = 21
        assert len(result["systems"]) == 21
        assert result["systems"][10]["_summary"] is True
        assert result["systems"][10]["skipped_count"] == 30


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_non_list_systems(self):
        """Should handle non-list gracefully."""
        data = {"systems": "not a list"}

        result = summarize_route(data)

        assert result["_meta"]["count"] == 1

    def test_missing_systems_key(self):
        """Should handle missing systems key."""
        data = {"route": []}

        result = summarize_route(data, systems_key="systems")

        assert result["_meta"]["count"] == 0

    def test_custom_systems_key(self):
        """Should use custom systems key."""
        data = {"route": _make_route(30)}

        result = summarize_route(data, systems_key="route", threshold=20)

        assert result["_meta"]["summarized"] is True
        assert len(result["route"]) == 11

    def test_preserves_other_fields(self):
        """Should preserve other fields in data."""
        data = {
            "systems": _make_route(30),
            "origin": "Jita",
            "destination": "Amarr",
            "jumps": 29,
        }

        result = summarize_route(data, threshold=20)

        assert result["origin"] == "Jita"
        assert result["destination"] == "Amarr"
        assert result["jumps"] == 29

    def test_head_tail_exceeds_route_length(self):
        """Should not summarize when head+tail >= route length."""
        # 25 systems, but head=15, tail=15 would cause overlap
        systems = _make_route(25)
        data = {"systems": systems}

        result = summarize_route(data, threshold=20, head=15, tail=15)

        # Should NOT summarize - returns original route
        assert len(result["systems"]) == 25
        assert "summarized" not in result["_meta"]

    def test_head_tail_equals_route_length(self):
        """Should not summarize when head+tail == route length."""
        systems = _make_route(22)
        data = {"systems": systems}

        result = summarize_route(data, threshold=20, head=11, tail=11)

        # Should NOT summarize - head+tail >= original_count
        assert len(result["systems"]) == 22
        assert "summarized" not in result["_meta"]


class TestPolicyIntegration:
    """Test integration with UNIVERSE policy constants."""

    def test_uses_policy_constants(self):
        """Should use constants from UNIVERSE policy."""
        # Verify constants exist
        assert UNIVERSE.ROUTE_SUMMARIZE_THRESHOLD == 20
        assert UNIVERSE.ROUTE_SHOW_HEAD == 5
        assert UNIVERSE.ROUTE_SHOW_TAIL == 5

    def test_default_parameters_match_policy(self):
        """Default parameters should match policy."""
        # Create route that would be summarized at threshold=20
        systems = _make_route(25)
        data = {"systems": systems}

        # Using defaults should summarize
        result = summarize_route(data)

        assert result["_meta"]["summarized"] is True
        # 5 + 1 + 5 = 11
        assert len(result["systems"]) == 11
