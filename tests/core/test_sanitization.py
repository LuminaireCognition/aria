"""
Tests for shared sanitization utilities.

Security: These tests verify that sensitive data is consistently redacted
across all logging paths. See dev/reviews/archive/SECURITY_000.md #5.
"""

from __future__ import annotations

from aria_esi.core.sanitization import (
    REDACTED,
    SENSITIVE_PATTERNS,
    sanitize_for_logging,
)


class TestSensitivePatterns:
    """Test that all expected patterns are covered."""

    def test_contains_core_patterns(self):
        """All core sensitive patterns are present."""
        for pattern in ("token", "password", "secret", "key", "auth", "credential"):
            assert pattern in SENSITIVE_PATTERNS


class TestSanitizeForLogging:
    """Test sanitize_for_logging function."""

    def test_redacts_exact_key_match(self):
        """Keys exactly matching a pattern are redacted."""
        result = sanitize_for_logging({"token": "abc123"})
        assert result["token"] == REDACTED

    def test_redacts_substring_match(self):
        """Keys containing a pattern as substring are redacted."""
        result = sanitize_for_logging({
            "api_token": "abc",
            "auth_header": "Bearer xyz",
            "client_secret": "s3cret",
            "access_key": "AKIA...",
            "user_password": "hunter2",
            "esi_credential": "cred123",
        })
        for key in result:
            assert result[key] == REDACTED, f"Expected {key} to be redacted"

    def test_case_insensitive(self):
        """Redaction is case-insensitive."""
        result = sanitize_for_logging({
            "API_TOKEN": "abc",
            "AuthHeader": "xyz",
            "ClientSecret": "s3cret",
        })
        for key in result:
            assert result[key] == REDACTED, f"Expected {key} to be redacted"

    def test_preserves_safe_keys(self):
        """Non-sensitive keys are preserved."""
        result = sanitize_for_logging({
            "action": "route",
            "origin": "Jita",
            "destination": "Amarr",
        })
        assert result == {
            "action": "route",
            "origin": "Jita",
            "destination": "Amarr",
        }

    def test_truncates_long_strings(self):
        """Strings longer than 200 chars are truncated."""
        long_value = "x" * 300
        result = sanitize_for_logging({"data": long_value})
        assert result["data"] == "x" * 200 + "..."
        assert len(result["data"]) == 203

    def test_preserves_short_strings(self):
        """Strings within the limit are preserved."""
        result = sanitize_for_logging({"data": "short"})
        assert result["data"] == "short"

    def test_summarizes_large_lists(self):
        """Lists with >10 items are summarized."""
        result = sanitize_for_logging({"items": list(range(25))})
        assert result["items"] == "[list of 25 items]"

    def test_preserves_small_lists(self):
        """Lists within limit are preserved."""
        result = sanitize_for_logging({"items": [1, 2, 3]})
        assert result["items"] == [1, 2, 3]

    def test_summarizes_large_dicts(self):
        """Dicts with >10 keys are summarized."""
        big_dict = {f"k{i}": i for i in range(15)}
        result = sanitize_for_logging({"config": big_dict})
        assert result["config"] == "{dict with 15 keys}"

    def test_preserves_small_dicts(self):
        """Dicts within limit are preserved."""
        small_dict = {"a": 1, "b": 2}
        result = sanitize_for_logging({"config": small_dict})
        assert result["config"] == {"a": 1, "b": 2}

    def test_empty_dict_returns_empty(self):
        """Empty input returns empty output."""
        assert sanitize_for_logging({}) == {}

    def test_redacts_not_drops(self):
        """Sensitive keys are redacted (value replaced), not dropped."""
        result = sanitize_for_logging({"api_token": "secret_value"})
        assert "api_token" in result
        assert result["api_token"] == REDACTED

    def test_mixed_sensitive_and_safe(self):
        """Mixed keys: sensitive redacted, safe preserved."""
        result = sanitize_for_logging({
            "action": "prices",
            "api_key": "AKIA...",
            "items": ["Tritanium"],
        })
        assert result["action"] == "prices"
        assert result["api_key"] == REDACTED
        assert result["items"] == ["Tritanium"]
