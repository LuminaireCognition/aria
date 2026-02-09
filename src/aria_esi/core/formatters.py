"""
ARIA ESI Formatters

Utility functions for formatting ESI data for display.
Consolidates previously duplicated formatting logic.
"""

from datetime import datetime, timezone
from typing import Optional

# =============================================================================
# ISK Formatting
# =============================================================================


def format_isk(value: float, precision: int = 2) -> str:
    """
    Format ISK value with appropriate suffix (B/M/K).

    Args:
        value: ISK amount
        precision: Decimal places (default: 2)

    Returns:
        Formatted string like "1.50B", "250.00M", "15.00K", "100.00"

    Examples:
        >>> format_isk(1500000000)
        '1.50B'
        >>> format_isk(250000000)
        '250.00M'
        >>> format_isk(15000)
        '15.00K'
        >>> format_isk(100)
        '100.00'
    """
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.{precision}f}B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.{precision}f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.{precision}f}K"
    elif value >= 1:
        return f"{value:.{precision}f}"
    else:
        # For sub-1 ISK values (rare), show more precision
        return f"{value:.4f}"


def format_isk_full(value: float) -> str:
    """
    Format ISK value with full number and commas.

    Args:
        value: ISK amount

    Returns:
        Formatted string like "1,500,000,000.00 ISK"
    """
    return f"{value:,.2f} ISK"


# =============================================================================
# Duration Formatting
# =============================================================================


def format_duration(seconds: float) -> str:
    """
    Format seconds into human-readable duration.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "5d 12h 30m", "2h 15m", "45m"

    Examples:
        >>> format_duration(86400 + 3600 + 1800)
        '1d 1h 30m'
        >>> format_duration(7200)
        '2h 0m'
        >>> format_duration(0)
        'Complete'
    """
    if seconds <= 0:
        return "Complete"

    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")

    return " ".join(parts)


def format_duration_long(seconds: float) -> str:
    """
    Format seconds into verbose duration.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "5 days, 12 hours, 30 minutes"
    """
    if seconds <= 0:
        return "Complete"

    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)

    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

    if not parts:
        return "Less than a minute"

    return ", ".join(parts)


# =============================================================================
# Skill Level Formatting
# =============================================================================

ROMAN_NUMERALS = ["0", "I", "II", "III", "IV", "V"]


def to_roman(level: int) -> str:
    """
    Convert skill level (0-5) to Roman numeral.

    Args:
        level: Skill level (0-5)

    Returns:
        Roman numeral string

    Examples:
        >>> to_roman(1)
        'I'
        >>> to_roman(5)
        'V'
        >>> to_roman(0)
        '0'
    """
    if 0 <= level <= 5:
        return ROMAN_NUMERALS[level]
    return str(level)


def format_skill_level(name: str, level: int) -> str:
    """
    Format skill name with level.

    Args:
        name: Skill name
        level: Skill level (0-5)

    Returns:
        Formatted string like "Drones V"
    """
    return f"{name} {to_roman(level)}"


# =============================================================================
# DateTime Parsing and Formatting
# =============================================================================


def parse_datetime(dt_str: str) -> Optional[datetime]:
    """
    Parse ESI datetime string to datetime object.

    Handles both formats: with and without microseconds.

    Args:
        dt_str: ISO format datetime string from ESI

    Returns:
        datetime object with UTC timezone, or None if parsing fails

    Examples:
        >>> parse_datetime("2026-01-15T12:30:00Z")
        datetime.datetime(2026, 1, 15, 12, 30, tzinfo=timezone.utc)
    """
    if not dt_str:
        return None

    # Handle both formats from ESI
    for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"]:
        try:
            return datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def format_datetime(dt: datetime) -> str:
    """
    Format datetime for display.

    Args:
        dt: datetime object

    Returns:
        ISO format string
    """
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def get_utc_now() -> datetime:
    """
    Get current UTC datetime.

    Returns:
        Current datetime with UTC timezone
    """
    return datetime.now(timezone.utc)


def get_utc_timestamp() -> str:
    """
    Get current UTC timestamp string.

    Returns:
        ISO format timestamp like "2026-01-15T12:30:00Z"
    """
    return format_datetime(get_utc_now())


def time_until(target: datetime) -> float:
    """
    Calculate seconds until target datetime.

    Args:
        target: Target datetime

    Returns:
        Seconds until target (negative if in past)
    """
    now = get_utc_now()
    return (target - now).total_seconds()


def time_since(target: datetime) -> float:
    """
    Calculate seconds since target datetime.

    Args:
        target: Target datetime

    Returns:
        Seconds since target (negative if in future)
    """
    return -time_until(target)


# =============================================================================
# Security Status Formatting
# =============================================================================


def format_security(sec_status: float) -> str:
    """
    Format security status for display.

    Args:
        sec_status: Security status (-1.0 to 1.0)

    Returns:
        Formatted string like "0.5", "-0.3", "1.0"
    """
    return f"{sec_status:.1f}"


def get_security_class(sec_status: float) -> str:
    """
    Get security classification from status.

    Args:
        sec_status: Security status

    Returns:
        "high_sec", "low_sec", or "null_sec"
    """
    if sec_status >= 0.45:  # 0.45 rounds to 0.5
        return "high_sec"
    elif sec_status >= 0.05:  # 0.05 rounds to 0.1
        return "low_sec"
    else:
        return "null_sec"


def get_security_description(sec_status: float) -> str:
    """
    Get human-readable security description.

    Args:
        sec_status: Character security status

    Returns:
        Description like "Paragon", "Neutral", "Outlaw"
    """
    if sec_status >= 5.0:
        return "Paragon"
    elif sec_status >= 2.0:
        return "Upstanding"
    elif sec_status >= 0.0:
        return "Neutral"
    elif sec_status >= -2.0:
        return "Suspect"
    elif sec_status >= -5.0:
        return "Criminal"
    else:
        return "Outlaw"


# =============================================================================
# Progress Formatting
# =============================================================================


def format_progress(current: float, total: float) -> str:
    """
    Format progress as percentage.

    Args:
        current: Current value
        total: Total value

    Returns:
        Percentage string like "75.5%"
    """
    if total <= 0:
        return "0.0%"
    percent = min(100.0, max(0.0, (current / total) * 100))
    return f"{percent:.1f}%"


def calculate_progress(start: datetime, end: datetime) -> float:
    """
    Calculate progress percentage between start and end times.

    Args:
        start: Start datetime
        end: End datetime

    Returns:
        Progress percentage (0.0 to 100.0)
    """
    now = get_utc_now()
    total = (end - start).total_seconds()
    elapsed = (now - start).total_seconds()

    if total <= 0:
        return 100.0

    return min(100.0, max(0.0, (elapsed / total) * 100))


# =============================================================================
# EFT (EVE Fitting Tool) Format
# =============================================================================


def format_eft_header(ship_type: str, fit_name: str = "ARIA Export") -> str:
    """
    Format EFT fitting header line.

    Args:
        ship_type: Ship type name
        fit_name: Fitting name

    Returns:
        Header line like "[Vexor, ARIA Export]"
    """
    return f"[{ship_type}, {fit_name}]"


def format_eft_drone(name: str, count: int) -> str:
    """
    Format drone line for EFT.

    Args:
        name: Drone type name
        count: Quantity

    Returns:
        Formatted line like "Hammerhead II x5"
    """
    return f"{name} x{count}"


def format_eft_cargo(name: str, count: int) -> str:
    """
    Format cargo line for EFT.

    Args:
        name: Item name
        count: Quantity

    Returns:
        Formatted line like "Antimatter Charge M x1000"
    """
    return f"{name} x{count}"


# =============================================================================
# Ref Type Formatting
# =============================================================================


def format_ref_type(ref_type: str) -> str:
    """
    Format wallet journal ref_type for display.

    Args:
        ref_type: Raw ref_type from ESI

    Returns:
        Human-readable name

    Examples:
        >>> format_ref_type("bounty_prizes")
        'Bounties'
        >>> format_ref_type("some_unknown_type")
        'Some Unknown Type'
    """
    from .constants import REF_TYPE_NAMES

    if ref_type in REF_TYPE_NAMES:
        return REF_TYPE_NAMES[ref_type]

    # Fallback: convert snake_case to Title Case
    return ref_type.replace("_", " ").title()
