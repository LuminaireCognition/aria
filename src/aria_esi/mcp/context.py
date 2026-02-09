"""
Context management utilities for MCP tool outputs.

Provides standardized metadata wrappers for tool responses to enable:
- Truncation tracking (count, truncated_from)
- Route summarization for long routes (head + summary + tail)
- Timestamp tracking for cache validity
- Consistent response structure across all dispatchers
- Structured logging for observability

Usage:
    from aria_esi.mcp.context import wrap_output, wrap_output_multi, summarize_route, OutputMeta

    # Basic wrapping with automatic truncation
    result = wrap_output({"systems": systems_list}, items_key="systems", max_items=50)

    # Multi-list wrapping (e.g., buy/sell orders)
    result = wrap_output_multi(
        {"buy_orders": buys, "sell_orders": sells},
        [("buy_orders", 20), ("sell_orders", 20)]
    )

    # Route summarization (long routes show head + summary + tail)
    result = summarize_route({"systems": route_systems}, threshold=20, head=5, tail=5)

    # Manual metadata attachment
    result["_meta"] = OutputMeta(count=len(items), truncated=True, truncated_from=100).to_dict()

    # Decorator for dispatcher logging
    @log_context("universe")
    async def universe(action: str, ...) -> dict:
        ...
"""

from __future__ import annotations

import functools
import json
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeVar

from ..core.logging import get_logger

logger = get_logger("aria_mcp.context")

# =============================================================================
# Trace Context
# =============================================================================

# Context variables for correlating LLM conversation turns with tool invocations
_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
_turn_id_var: ContextVar[int | None] = ContextVar("turn_id", default=None)


def set_trace_context(trace_id: str | None = None, turn_id: int | None = None) -> None:
    """
    Set trace context for the current request.

    Call this at the start of a tool invocation to correlate logs
    with the LLM conversation turn.

    Args:
        trace_id: Unique identifier for the conversation/session
        turn_id: Sequential turn number within the conversation
    """
    _trace_id_var.set(trace_id)
    _turn_id_var.set(turn_id)


def get_trace_context() -> dict[str, Any]:
    """
    Get the current trace context.

    Returns:
        Dictionary with trace_id and turn_id (may be None if not set)
    """
    return {
        "trace_id": _trace_id_var.get(),
        "turn_id": _turn_id_var.get(),
    }


def reset_trace_context() -> None:
    """
    Reset trace context at end of request.

    Call this to clear trace context when a request completes.
    """
    _trace_id_var.set(None)
    _turn_id_var.set(None)


# Type variable for decorator
F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class OutputMeta:
    """
    Metadata for tool outputs.

    Tracks item count, truncation status, timestamp, and provenance for all tool responses.

    Attributes:
        count: Number of items in the (possibly truncated) output
        truncated: Whether the output was truncated from a larger result
        truncated_from: Original count before truncation (if truncated)
        timestamp: ISO timestamp when output was generated
        source: Data source identifier (e.g., "sde", "fuzzwork", "esi", "eos")
        as_of: ISO timestamp of source data freshness
    """

    count: int
    truncated: bool = False
    truncated_from: int | None = None
    timestamp: str = field(default_factory=lambda: "")
    source: str | None = None
    as_of: str | None = None

    def __post_init__(self) -> None:
        """Set timestamp if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with count, timestamp, optional truncation fields, and provenance
        """
        d: dict[str, Any] = {"count": self.count, "timestamp": self.timestamp}
        if self.truncated:
            d["truncated"] = True
            d["truncated_from"] = self.truncated_from
        if self.source is not None:
            d["source"] = self.source
        if self.as_of is not None:
            d["as_of"] = self.as_of
        return d


def _enforce_output_bytes(
    data: dict[str, Any],
    items_key: str,
    max_bytes: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Enforce per-tool byte size limits by iteratively truncating list items.

    Measures serialized JSON size and truncates list items until output
    is under the configured byte limit.

    Args:
        data: Tool output dictionary containing a list to potentially truncate
        items_key: Key in data dict containing the list of items
        max_bytes: Maximum output size in bytes (defaults to GLOBAL.MAX_OUTPUT_SIZE_BYTES)

    Returns:
        Tuple of (modified data dict, byte_enforcement_meta dict)
        byte_enforcement_meta contains:
        - byte_limit_enforced: True if byte truncation was applied
        - original_bytes: Original size before byte enforcement
        - final_bytes: Size after enforcement
    """
    from .context_policy import GLOBAL

    if max_bytes is None:
        max_bytes = GLOBAL.MAX_OUTPUT_SIZE_BYTES

    enforcement_meta: dict[str, Any] = {}

    items = data.get(items_key, [])
    if not isinstance(items, list) or len(items) == 0:
        return data, enforcement_meta

    # Measure original size
    try:
        original_bytes = len(json.dumps(data))
    except (TypeError, ValueError):
        return data, enforcement_meta

    if original_bytes <= max_bytes:
        return data, enforcement_meta

    # Record original size and start truncating
    enforcement_meta["original_bytes"] = original_bytes

    # Binary search for the right number of items
    low, high = 1, len(items)
    best_count = 1

    while low <= high:
        mid = (low + high) // 2
        data[items_key] = items[:mid]
        try:
            current_bytes = len(json.dumps(data))
        except (TypeError, ValueError):
            break

        if current_bytes <= max_bytes:
            best_count = mid
            low = mid + 1
        else:
            high = mid - 1

    # Apply the best truncation
    data[items_key] = items[:best_count]
    try:
        final_bytes = len(json.dumps(data))
    except (TypeError, ValueError):
        final_bytes = 0

    enforcement_meta["byte_limit_enforced"] = True
    enforcement_meta["final_bytes"] = final_bytes

    return data, enforcement_meta


def _enforce_output_bytes_multi(
    data: dict[str, Any],
    items_config: list[tuple[str, int]],
    max_bytes: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Enforce per-tool byte size limits for multi-list outputs.

    Iteratively truncates the largest list first until output is under
    the configured byte limit.

    Args:
        data: Tool output dictionary containing multiple lists
        items_config: List of (key, max_items) tuples for each list
        max_bytes: Maximum output size in bytes (defaults to GLOBAL.MAX_OUTPUT_SIZE_BYTES)

    Returns:
        Tuple of (modified data dict, byte_enforcement_meta dict)
    """
    from .context_policy import GLOBAL

    if max_bytes is None:
        max_bytes = GLOBAL.MAX_OUTPUT_SIZE_BYTES

    enforcement_meta: dict[str, Any] = {}

    # Measure original size
    try:
        original_bytes = len(json.dumps(data))
    except (TypeError, ValueError):
        return data, enforcement_meta

    if original_bytes <= max_bytes:
        return data, enforcement_meta

    enforcement_meta["original_bytes"] = original_bytes

    # Get list sizes
    list_keys = [key for key, _ in items_config]
    list_lengths = {
        key: len(data.get(key, [])) for key in list_keys if isinstance(data.get(key), list)
    }

    if not list_lengths:
        return data, enforcement_meta

    # Iteratively truncate largest list until under limit
    max_iterations = 100
    for _ in range(max_iterations):
        try:
            current_bytes = len(json.dumps(data))
        except (TypeError, ValueError):
            break

        if current_bytes <= max_bytes:
            break

        # Find the largest list
        largest_key = max(list_lengths, key=lambda k: list_lengths.get(k, 0))
        current_len = list_lengths.get(largest_key, 0)

        if current_len <= 1:
            # Can't truncate further
            break

        # Truncate by 20% or at least 1 item
        new_len = max(1, int(current_len * 0.8))
        data[largest_key] = data[largest_key][:new_len]
        list_lengths[largest_key] = new_len

    try:
        final_bytes = len(json.dumps(data))
    except (TypeError, ValueError):
        final_bytes = 0

    enforcement_meta["byte_limit_enforced"] = True
    enforcement_meta["final_bytes"] = final_bytes

    return data, enforcement_meta


def wrap_output(
    data: dict[str, Any],
    items_key: str,
    max_items: int = 50,
    source: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """
    Wrap tool output with metadata and optional truncation.

    Automatically truncates lists exceeding max_items, enforces byte limits,
    and adds _meta field with count, truncation status, timestamp, and provenance.

    Args:
        data: Tool output dictionary containing a list to potentially truncate
        items_key: Key in data dict containing the list of items
        max_items: Maximum items to return (default 50)
        source: Data source identifier (e.g., "sde", "fuzzwork", "esi", "eos")
        as_of: ISO timestamp of source data freshness

    Returns:
        Modified data dict with truncated list and _meta field

    Example:
        >>> result = {"systems": [{"name": "Jita"}, {"name": "Amarr"}, ...]}
        >>> wrapped = wrap_output(result, "systems", max_items=10)
        >>> wrapped["_meta"]
        {'count': 10, 'truncated': True, 'truncated_from': 50, 'timestamp': '...'}
    """
    items = data.get(items_key, [])

    # Handle non-list items gracefully
    if not isinstance(items, list):
        data["_meta"] = OutputMeta(
            count=1 if items else 0,
            source=source,
            as_of=as_of,
        ).to_dict()
        return data

    original_count = len(items)
    truncated = original_count > max_items

    if truncated:
        items = items[:max_items]
        data[items_key] = items

    # Enforce byte limits after item truncation
    data, byte_meta = _enforce_output_bytes(data, items_key)

    # Refresh item count after potential byte enforcement
    items = data.get(items_key, [])

    data["_meta"] = OutputMeta(
        count=len(items),
        truncated=truncated or byte_meta.get("byte_limit_enforced", False),
        truncated_from=original_count
        if truncated or byte_meta.get("byte_limit_enforced")
        else None,
        source=source,
        as_of=as_of,
    ).to_dict()

    # Add byte enforcement metadata if applicable
    if byte_meta.get("byte_limit_enforced"):
        data["_meta"]["byte_limit_enforced"] = True
        data["_meta"]["original_bytes"] = byte_meta.get("original_bytes")

    return data


def wrap_scalar_output(
    data: dict[str, Any],
    count: int | None = None,
    source: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """
    Wrap non-list tool output with metadata.

    For tool responses that don't contain truncatable lists but
    still need metadata tracking.

    Args:
        data: Tool output dictionary
        count: Optional item count (defaults to 1 for non-empty, 0 for empty)
        source: Data source identifier (e.g., "sde", "fuzzwork", "esi", "eos")
        as_of: ISO timestamp of source data freshness

    Returns:
        Modified data dict with _meta field

    Example:
        >>> result = {"item": {"name": "Tritanium", "type_id": 34}}
        >>> wrapped = wrap_scalar_output(result)
        >>> wrapped["_meta"]
        {'count': 1, 'timestamp': '...'}
    """
    if count is None:
        # Estimate count based on presence of data
        count = 1 if any(v for v in data.values() if v is not None) else 0

    data["_meta"] = OutputMeta(count=count, source=source, as_of=as_of).to_dict()
    return data


def create_error_meta(error_code: str, message: str, max_message_len: int = 500) -> dict[str, Any]:
    """
    Create standardized error metadata.

    Args:
        error_code: Short error code for programmatic handling
        message: Human-readable error message
        max_message_len: Maximum length for error message (default 500)

    Returns:
        Dictionary with error fields and _meta

    Example:
        >>> create_error_meta("NOT_FOUND", "System 'Xyzzy' not found in universe")
        {'error': True, 'error_code': 'NOT_FOUND', 'message': '...', '_meta': {...}}
    """
    # Truncate message if too long
    if len(message) > max_message_len:
        message = message[: max_message_len - 3] + "..."

    return {
        "error": True,
        "error_code": error_code,
        "message": message,
        "_meta": OutputMeta(count=0).to_dict(),
    }


def wrap_output_multi(
    data: dict[str, Any],
    items_config: list[tuple[str, int]],
    source: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """
    Wrap tool output with metadata for multiple truncatable lists.

    For outputs containing multiple lists that may need truncation,
    such as market orders (buy_orders, sell_orders) or FW frontlines
    (contested, vulnerable, stable).

    Args:
        data: Tool output dictionary containing multiple lists
        items_config: List of (key, max_items) tuples specifying
                     each list to potentially truncate
        source: Data source identifier (e.g., "sde", "fuzzwork", "esi", "eos")
        as_of: ISO timestamp of source data freshness

    Returns:
        Modified data dict with truncated lists and combined _meta field

    Example:
        >>> result = {
        ...     "buy_orders": [...100 orders...],
        ...     "sell_orders": [...50 orders...]
        ... }
        >>> wrapped = wrap_output_multi(result, [("buy_orders", 20), ("sell_orders", 20)])
        >>> wrapped["_meta"]
        {
            'lists': {
                'buy_orders': {'count': 20, 'truncated': True, 'truncated_from': 100},
                'sell_orders': {'count': 20, 'truncated': True, 'truncated_from': 50}
            },
            'total_count': 40,
            'truncated': True,
            'timestamp': '...'
        }
    """
    lists_meta: dict[str, dict[str, Any]] = {}
    total_count = 0
    any_truncated = False

    for key, max_items in items_config:
        items = data.get(key, [])

        # Handle non-list items gracefully
        if not isinstance(items, list):
            lists_meta[key] = {"count": 1 if items else 0, "truncated": False}
            total_count += 1 if items else 0
            continue

        original_count = len(items)
        truncated = original_count > max_items

        if truncated:
            items = items[:max_items]
            data[key] = items
            any_truncated = True

        list_meta: dict[str, Any] = {
            "count": len(items),
            "truncated": truncated,
        }
        if truncated:
            list_meta["truncated_from"] = original_count

        lists_meta[key] = list_meta
        total_count += len(items)

    # Enforce byte limits after item truncation
    data, byte_meta = _enforce_output_bytes_multi(data, items_config)

    # Recalculate counts after byte enforcement
    if byte_meta.get("byte_limit_enforced"):
        any_truncated = True
        total_count = 0
        for key, _ in items_config:
            items = data.get(key, [])
            if isinstance(items, list):
                new_count = len(items)
                if key in lists_meta:
                    old_count = lists_meta[key]["count"]
                    if new_count < old_count:
                        lists_meta[key]["truncated"] = True
                        if "truncated_from" not in lists_meta[key]:
                            lists_meta[key]["truncated_from"] = old_count
                    lists_meta[key]["count"] = new_count
                total_count += new_count
            else:
                total_count += lists_meta.get(key, {}).get("count", 0)

    meta: dict[str, Any] = {
        "lists": lists_meta,
        "total_count": total_count,
        "truncated": any_truncated,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    # Add provenance if provided
    if source is not None:
        meta["source"] = source
    if as_of is not None:
        meta["as_of"] = as_of

    # Add byte enforcement metadata if applicable
    if byte_meta.get("byte_limit_enforced"):
        meta["byte_limit_enforced"] = True
        meta["original_bytes"] = byte_meta.get("original_bytes")

    data["_meta"] = meta

    return data


def summarize_route(
    data: dict[str, Any],
    systems_key: str = "systems",
    threshold: int = 20,
    head: int = 5,
    tail: int = 5,
) -> dict[str, Any]:
    """
    Summarize route by compressing middle section for long routes.

    For routes > threshold:
    - Keep first `head` systems with full detail
    - Replace middle with summary dict containing security breakdown
    - Keep last `tail` systems with full detail

    Args:
        data: Route result dictionary containing systems list
        systems_key: Key in data dict containing the route systems list
        threshold: Routes longer than this get summarized
        head: Number of systems to keep at start
        tail: Number of systems to keep at end

    Returns:
        Modified data dict with summarized route and _meta field

    Example:
        >>> result = {"systems": [...45 systems...], "jumps": 44}
        >>> summarized = summarize_route(result, threshold=20, head=5, tail=5)
        >>> len(summarized["systems"])  # 5 + 1 (summary) + 5 = 11
        11
    """
    systems = data.get(systems_key, [])

    # Handle non-list or empty
    if not isinstance(systems, list):
        data["_meta"] = OutputMeta(count=1 if systems else 0).to_dict()
        return data

    original_count = len(systems)

    # Short routes: no summarization needed
    if original_count <= threshold:
        data["_meta"] = OutputMeta(count=original_count).to_dict()
        return data

    # Validate head + tail doesn't exceed route length (defensive check)
    # This ensures we don't create overlapping head/tail sections
    if head + tail >= original_count:
        # Can't summarize - head+tail would overlap or exceed route
        data["_meta"] = OutputMeta(count=original_count).to_dict()
        return data

    # Long routes: summarize middle section
    head_systems = systems[:head]
    middle_systems = systems[head:-tail]
    tail_systems = systems[-tail:]

    # Build security breakdown for middle section
    security_breakdown = {"highsec": 0, "lowsec": 0, "nullsec": 0}
    lowest_security = 1.1  # Start above max possible
    lowest_security_system = None

    for system in middle_systems:
        # Handle both dict and object formats
        if isinstance(system, dict):
            sec = system.get("security", 1.0)
            name = system.get("name", "Unknown")
        else:
            sec = getattr(system, "security", 1.0)
            name = getattr(system, "name", "Unknown")

        # Classify security
        if sec >= 0.45:
            security_breakdown["highsec"] += 1
        elif sec > 0.0:
            security_breakdown["lowsec"] += 1
        else:
            security_breakdown["nullsec"] += 1

        # Track lowest security
        if sec < lowest_security:
            lowest_security = sec
            lowest_security_system = name

    # Build summary entry
    summary = {
        "_summary": True,
        "skipped_count": len(middle_systems),
        "security_breakdown": security_breakdown,
        "lowest_security": round(lowest_security, 2) if lowest_security <= 1.0 else None,
        "lowest_security_system": lowest_security_system,
    }

    # Reconstruct route with summary
    data[systems_key] = head_systems + [summary] + tail_systems

    # Set metadata
    data["_meta"] = OutputMeta(
        count=len(data[systems_key]),
        truncated=False,  # Not truncated, summarized
    ).to_dict()
    data["_meta"]["summarized"] = True
    data["_meta"]["original_count"] = original_count

    return data


def _sanitize_params(params: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize parameters for logging.

    Removes potentially sensitive data and truncates large values.

    Args:
        params: Raw parameter dictionary

    Returns:
        Sanitized copy safe for logging
    """
    sanitized = {}
    sensitive_keys = {"token", "password", "secret", "key", "auth"}

    for key, value in params.items():
        key_lower = key.lower()

        # Skip sensitive keys
        if any(s in key_lower for s in sensitive_keys):
            sanitized[key] = "[REDACTED]"
            continue

        # Truncate large strings
        if isinstance(value, str) and len(value) > 200:
            sanitized[key] = value[:200] + "..."
        # Truncate large lists
        elif isinstance(value, list) and len(value) > 10:
            sanitized[key] = f"[list of {len(value)} items]"
        # Truncate large dicts
        elif isinstance(value, dict) and len(value) > 10:
            sanitized[key] = f"{{dict with {len(value)} keys}}"
        else:
            sanitized[key] = value

    return sanitized


def log_context(dispatcher: str) -> Callable[[F], F]:
    """
    Decorator for MCP dispatcher context logging.

    Provides structured logging for MCP tool calls including:
    - Action name and sanitized parameters
    - Execution time
    - Output metadata (count, truncation status)
    - Context budget tracking and warnings
    - Trace context (trace_id, turn_id) for correlation

    The logging level is DEBUG for start messages and INFO for completion.
    Enable JSON logging via ARIA_LOG_JSON=1 environment variable.

    Args:
        dispatcher: Name of the dispatcher (e.g., "universe", "market")

    Returns:
        Decorator function

    Example:
        @server.tool()
        @log_context("universe")
        async def universe(action: str, ...) -> dict:
            ...
    """
    from .context_budget import get_context_budget

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            action = kwargs.get("action", "unknown")
            start = time.perf_counter()

            # Check for trace context in kwargs (allows callers to set)
            if "_trace_id" in kwargs or "_turn_id" in kwargs:
                set_trace_context(
                    trace_id=kwargs.pop("_trace_id", None),
                    turn_id=kwargs.pop("_turn_id", None),
                )

            # Get current trace context for logging
            trace_ctx = get_trace_context()

            # Build extra dict with trace context
            start_extra: dict[str, Any] = {
                "dispatcher": dispatcher,
                "action": action,
                "params": _sanitize_params(kwargs),
            }
            if trace_ctx["trace_id"] is not None:
                start_extra["trace_id"] = trace_ctx["trace_id"]
            if trace_ctx["turn_id"] is not None:
                start_extra["turn_id"] = trace_ctx["turn_id"]

            # Log call start at DEBUG level
            logger.debug("MCP call start", extra=start_extra)

            try:
                result = await func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000

                # Track output in context budget
                output_bytes = 0
                if isinstance(result, dict):
                    try:
                        output_bytes = len(json.dumps(result))
                    except (TypeError, ValueError):
                        output_bytes = 0

                budget = get_context_budget()
                budget.add_output(output_bytes)

                # Check budget limits and add warning if needed
                limits = budget.check_limits()
                if limits.get("warning") and isinstance(result, dict):
                    if "_meta" not in result:
                        result["_meta"] = {}
                    result["_meta"]["budget_warning"] = limits["warning"]
                    result["_meta"]["budget_bytes_used"] = limits["bytes_used"]

                # Extract metadata from result
                meta = result.get("_meta", {}) if isinstance(result, dict) else {}

                # Handle both single and multi-list metadata
                if "lists" in meta:
                    output_count = meta.get("total_count", 0)
                else:
                    output_count = meta.get("count", 0)

                truncated = meta.get("truncated", False)

                # Build completion log extra with trace context
                complete_extra: dict[str, Any] = {
                    "dispatcher": dispatcher,
                    "action": action,
                    "elapsed_ms": round(elapsed_ms, 2),
                    "output_count": output_count,
                    "truncated": truncated,
                    "output_bytes": output_bytes,
                    "budget_bytes_used": budget.bytes_used,
                }
                if trace_ctx["trace_id"] is not None:
                    complete_extra["trace_id"] = trace_ctx["trace_id"]
                if trace_ctx["turn_id"] is not None:
                    complete_extra["turn_id"] = trace_ctx["turn_id"]

                # Log completion at INFO level
                logger.info("MCP call complete", extra=complete_extra)

                return result

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start) * 1000

                # Build error log extra with trace context
                error_extra: dict[str, Any] = {
                    "dispatcher": dispatcher,
                    "action": action,
                    "elapsed_ms": round(elapsed_ms, 2),
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
                if trace_ctx["trace_id"] is not None:
                    error_extra["trace_id"] = trace_ctx["trace_id"]
                if trace_ctx["turn_id"] is not None:
                    error_extra["turn_id"] = trace_ctx["turn_id"]

                # Log error
                logger.warning("MCP call failed", extra=error_extra)
                raise

        return wrapper  # type: ignore[return-value]

    return decorator
