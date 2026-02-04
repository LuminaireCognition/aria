"""
ARIA ESI Centralized Configuration

Provides validated, type-safe access to all environment variables using Pydantic Settings.
All environment variables are validated at import time with helpful error messages.

Usage:
    from aria_esi.core.config import get_settings

    settings = get_settings()
    if settings.log_level == "DEBUG":
        ...

Data Paths:
    All data is stored in {instance_root}/cache/:
    - cache/aria.db: Market database
    - cache/eos-data/: EOS fitting data
    - cache/killmails.db: Killmail store

Environment Variables:
    ARIA_LOG_LEVEL: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    ARIA_DEBUG: Legacy debug flag (enables DEBUG level if set)
    ARIA_LOG_JSON: Output logs as JSON
    ARIA_PILOT: Active character ID override
    ARIA_NO_KEYRING: Disable system keyring
    ARIA_NO_RETRY: Disable HTTP retry logic
    ARIA_ALLOW_UNSAFE_PATHS: Bypass path security validation
    ARIA_ALLOW_UNPINNED: Bypass data integrity checks
    ARIA_MCP_POLICY: Custom MCP policy file path
    ARIA_MCP_BYPASS_POLICY: Bypass MCP policy checks
    ARIA_UNIVERSE_GRAPH: Custom universe graph path
    ARIA_UNIVERSE_LOG_LEVEL: MCP server log level
    ARIA_DEBUG_TIMING: Enable timing debug logs

External API Keys (no ARIA_ prefix):
    ANTHROPIC_API_KEY: Anthropic API key for LLM commentary generation
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_env_file() -> Path | None:
    """
    Find .env file by searching for project root markers.

    Searches upward from this file's location for pyproject.toml,
    then checks for .env in that directory.

    Returns:
        Path to .env if found, None otherwise
    """
    # Start from this file's directory
    current = Path(__file__).resolve().parent

    # Walk up to find project root (marked by pyproject.toml)
    for _ in range(10):  # Limit search depth
        if (current / "pyproject.toml").exists():
            env_file = current / ".env"
            if env_file.exists():
                return env_file
            return None  # Project root found but no .env
        parent = current.parent
        if parent == current:
            break  # Reached filesystem root
        current = parent

    return None


def _find_instance_root() -> Path:
    """
    Find the ARIA instance root directory.

    Resolution order:
    1. ARIA_INSTANCE_ROOT environment variable (explicit override)
    2. Project root (directory containing pyproject.toml)
    3. Current working directory (fallback)

    Returns:
        Path to instance root directory
    """
    import os

    # Check for explicit override
    override = os.environ.get("ARIA_INSTANCE_ROOT")
    if override:
        return Path(override)

    # Search for project root (reuse logic from _find_project_env_file)
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    # Ultimate fallback
    return Path.cwd()


# Resolve paths at module load time
_ENV_FILE = _find_project_env_file()
_INSTANCE_ROOT = _find_instance_root()


class AriaSettings(BaseSettings):
    """
    ARIA configuration settings with validation.

    Environment variables are automatically loaded with the ARIA_ prefix.
    All settings have sensible defaults and validation.
    """

    model_config = SettingsConfigDict(
        env_prefix="ARIA_",
        env_file=_ENV_FILE,  # Use resolved project .env path
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore unknown env vars
        case_sensitive=False,  # Allow ARIA_LOG_LEVEL or aria_log_level
    )

    # =========================================================================
    # Logging Configuration
    # =========================================================================

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="WARNING",
        description="Log level for ARIA components",
    )

    debug: bool = Field(
        default=False,
        description="Legacy debug flag (enables DEBUG level if set)",
    )

    log_json: bool = Field(
        default=False,
        description="Output logs in JSON format for machine parsing",
    )

    debug_timing: bool = Field(
        default=False,
        description="Enable timing debug logs for performance analysis",
    )

    # =========================================================================
    # Authentication & Identity
    # =========================================================================

    pilot: Optional[str] = Field(
        default=None,
        description="Active character ID override (bypasses config.json)",
    )

    # =========================================================================
    # Optional Dependencies
    # =========================================================================

    no_keyring: bool = Field(
        default=False,
        description="Disable system keyring credential storage",
    )

    no_retry: bool = Field(
        default=False,
        description="Disable HTTP retry logic (tenacity)",
    )

    # =========================================================================
    # Security & Integrity Overrides (Break-Glass)
    # =========================================================================

    allow_unsafe_paths: bool = Field(
        default=False,
        description="Bypass path security validation (DANGEROUS)",
    )

    allow_unpinned: bool = Field(
        default=False,
        description="Bypass data integrity verification (DANGEROUS)",
    )

    # =========================================================================
    # MCP Server Configuration
    # =========================================================================

    mcp_policy: Optional[Path] = Field(
        default=None,
        description="Custom MCP policy file path",
    )

    mcp_bypass_policy: bool = Field(
        default=False,
        description="Bypass MCP capability policy checks",
    )

    universe_graph: Optional[Path] = Field(
        default=None,
        description="Custom universe graph file path",
    )

    universe_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="WARNING",
        description="MCP universe server log level",
    )

    # =========================================================================
    # External API Keys (loaded without ARIA_ prefix)
    # =========================================================================

    anthropic_api_key: Optional[str] = Field(
        default=None,
        validation_alias="ANTHROPIC_API_KEY",
        description="Anthropic API key for LLM commentary generation",
    )

    # =========================================================================
    # Data Paths
    # =========================================================================

    instance_root: Path = Field(
        default=_INSTANCE_ROOT,
        description="Instance root directory (project root containing pyproject.toml)",
    )

    # =========================================================================
    # RedisQ Real-Time Intel Configuration
    # =========================================================================

    redisq_enabled: bool = Field(
        default=False,
        description="Enable RedisQ real-time killmail streaming",
    )

    redisq_regions: list[int] = Field(
        default_factory=list,
        description="Region IDs to filter kills (empty = all regions)",
    )

    redisq_min_value: int = Field(
        default=0,
        description="Minimum kill value in ISK to process (0 = no filter)",
    )

    redisq_retention_hours: int = Field(
        default=24,
        description="Hours to retain realtime kill data before cleanup",
    )

    # =========================================================================
    # Validators
    # =========================================================================

    @field_validator("log_level", "universe_log_level", mode="before")
    @classmethod
    def uppercase_log_level(cls, v: str) -> str:
        """Normalize log level to uppercase."""
        if isinstance(v, str):
            return v.upper()
        return v

    # =========================================================================
    # Computed Properties
    # =========================================================================

    @property
    def effective_log_level(self) -> str:
        """
        Get effective log level, respecting legacy ARIA_DEBUG.

        Priority:
        1. Explicit ARIA_LOG_LEVEL
        2. ARIA_DEBUG=1 → DEBUG
        3. Default: WARNING
        """
        if self.debug and self.log_level == "WARNING":
            # Only apply debug override if log_level wasn't explicitly set
            return "DEBUG"
        return self.log_level

    @property
    def log_level_int(self) -> int:
        """Get effective log level as logging constant."""
        return getattr(logging, self.effective_log_level)

    @property
    def eos_data_path(self) -> Path:
        """Path to EOS fitting data directory."""
        return self.instance_root / "cache" / "eos-data"

    @property
    def db_path(self) -> Path:
        """Path to market database."""
        return self.instance_root / "cache" / "aria.db"

    @property
    def killmail_db_path(self) -> Path:
        """Path to killmail database."""
        return self.instance_root / "cache" / "killmails.db"

    @property
    def cache_dir(self) -> Path:
        """Path to cache directory."""
        return self.instance_root / "cache"

    def is_break_glass_enabled(self, feature: str) -> bool:
        """
        Check if break-glass mode is enabled for a security feature.

        Args:
            feature: One of "paths", "integrity", "policy"

        Returns:
            True if the bypass is enabled
        """
        if feature == "paths":
            return self.allow_unsafe_paths
        elif feature == "integrity":
            return self.allow_unpinned
        elif feature == "policy":
            return self.mcp_bypass_policy
        else:
            return False


# =============================================================================
# Singleton Accessor
# =============================================================================


@lru_cache(maxsize=1)
def get_settings() -> AriaSettings:
    """
    Get the singleton settings instance.

    Uses lru_cache to ensure settings are only loaded once.
    The settings are validated at first access.

    Returns:
        AriaSettings instance with validated configuration
    """
    return AriaSettings()


def reset_settings() -> None:
    """
    Reset the settings cache (for testing).

    After calling this, the next get_settings() call will
    reload settings from environment variables.
    """
    get_settings.cache_clear()


# =============================================================================
# Convenience Functions
# =============================================================================


def is_debug_enabled() -> bool:
    """Check if debug logging is enabled."""
    return get_settings().effective_log_level == "DEBUG"


def is_json_logging() -> bool:
    """Check if JSON logging is enabled."""
    return get_settings().log_json


def is_keyring_disabled() -> bool:
    """Check if keyring is disabled via environment."""
    return get_settings().no_keyring


def is_retry_disabled() -> bool:
    """Check if retry logic is disabled via environment."""
    return get_settings().no_retry
