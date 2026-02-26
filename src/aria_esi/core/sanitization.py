"""
Shared sanitization utilities for logging and audit trails.

Provides consistent redaction of sensitive fields across all ARIA modules.
All modules that log request parameters or context should use sanitize_for_logging()
to prevent accidental credential leakage.

Security finding: #5 from dev/reviews/archive/SECURITY_000.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# Sensitive key patterns — any key whose lowercase form contains one of these
# will have its value redacted. Uses substring matching for resilience against
# variations like "api_key", "auth_token", "client_secret", etc.
SENSITIVE_PATTERNS: frozenset[str] = frozenset(
    {"token", "password", "secret", "key", "auth", "credential"}
)

REDACTED = "[REDACTED]"

# Maximum length for string values before truncation
_MAX_STRING_LENGTH = 200

# Maximum collection size before summarization
_MAX_LIST_LENGTH = 10
_MAX_DICT_LENGTH = 10


def sanitize_for_logging(params: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize a dictionary for safe logging.

    - Keys matching sensitive patterns (substring, case-insensitive) are redacted
    - Large strings are truncated
    - Large lists/dicts are summarized

    Args:
        params: Raw parameter dictionary

    Returns:
        Sanitized copy safe for logging
    """
    sanitized: dict[str, Any] = {}

    for key, value in params.items():
        key_lower = key.lower()

        # Redact sensitive keys (substring match)
        if any(pattern in key_lower for pattern in SENSITIVE_PATTERNS):
            sanitized[key] = REDACTED
            continue

        # Truncate large strings
        if isinstance(value, str) and len(value) > _MAX_STRING_LENGTH:
            sanitized[key] = value[:_MAX_STRING_LENGTH] + "..."
        # Summarize large lists
        elif isinstance(value, list) and len(value) > _MAX_LIST_LENGTH:
            sanitized[key] = f"[list of {len(value)} items]"
        # Summarize large dicts
        elif isinstance(value, dict) and len(value) > _MAX_DICT_LENGTH:
            sanitized[key] = f"{{dict with {len(value)} keys}}"
        else:
            sanitized[key] = value

    return sanitized
