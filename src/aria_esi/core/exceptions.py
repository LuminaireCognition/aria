"""
ARIA Base Exceptions

Project-wide exception hierarchy root. All ARIA domain exceptions
should inherit from AriaError to enable unified error handling.
"""

from __future__ import annotations


class AriaError(Exception):
    """Base exception for all ARIA errors."""

    pass
