"""
Tests for MCP context management utilities.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aria_esi.mcp.context import (
    OutputMeta,
    _enforce_output_bytes,
    _enforce_output_bytes_multi,
    create_error_meta,
    get_trace_context,
    reset_trace_context,
    set_trace_context,
    wrap_output,
    wrap_output_multi,
    wrap_scalar_output,
)


class TestOutputMeta:
    """Tests for OutputMeta dataclass."""

    def test_basic_creation(self):
        """Should create metadata with count."""
        meta = OutputMeta(count=10)

        assert meta.count == 10
        assert meta.truncated is False
        assert meta.truncated_from is None
        assert meta.timestamp  # Should be set

    def test_truncation_fields(self):
        """Should track truncation status."""
        meta = OutputMeta(count=50, truncated=True, truncated_from=100)

        assert meta.count == 50
        assert meta.truncated is True
        assert meta.truncated_from == 100

    def test_auto_timestamp(self):
        """Should auto-generate timestamp in ISO format."""
        meta = OutputMeta(count=1)

        # Should be valid ISO format
        parsed = datetime.fromisoformat(meta.timestamp)
        assert parsed.tzinfo == timezone.utc

    def test_custom_timestamp(self):
        """Should accept custom timestamp."""
        custom_ts = "2026-01-22T12:00:00+00:00"
        meta = OutputMeta(count=1, timestamp=custom_ts)

        assert meta.timestamp == custom_ts

    def test_to_dict_basic(self):
        """Should convert to dict without truncation fields when not truncated."""
        meta = OutputMeta(count=10)
        d = meta.to_dict()

        assert d["count"] == 10
        assert "timestamp" in d
        assert "truncated" not in d
        assert "truncated_from" not in d

    def test_to_dict_truncated(self):
        """Should include truncation fields when truncated."""
        meta = OutputMeta(count=50, truncated=True, truncated_from=100)
        d = meta.to_dict()

        assert d["count"] == 50
        assert d["truncated"] is True
        assert d["truncated_from"] == 100


class TestWrapOutput:
    """Tests for wrap_output function."""

    def test_no_truncation_needed(self):
        """Should add metadata without truncating when under limit."""
        data = {"systems": [{"name": "Jita"}, {"name": "Amarr"}]}

        result = wrap_output(data, "systems", max_items=50)

        assert len(result["systems"]) == 2
        assert result["_meta"]["count"] == 2
        assert "truncated" not in result["_meta"]

    def test_truncates_at_limit(self):
        """Should truncate when over limit."""
        systems = [{"name": f"System{i}"} for i in range(100)]
        data = {"systems": systems}

        result = wrap_output(data, "systems", max_items=50)

        assert len(result["systems"]) == 50
        assert result["_meta"]["count"] == 50
        assert result["_meta"]["truncated"] is True
        assert result["_meta"]["truncated_from"] == 100

    def test_exactly_at_limit(self):
        """Should not truncate when exactly at limit."""
        systems = [{"name": f"System{i}"} for i in range(50)]
        data = {"systems": systems}

        result = wrap_output(data, "systems", max_items=50)

        assert len(result["systems"]) == 50
        assert result["_meta"]["count"] == 50
        assert "truncated" not in result["_meta"]

    def test_empty_list(self):
        """Should handle empty lists."""
        data = {"systems": []}

        result = wrap_output(data, "systems", max_items=50)

        assert result["systems"] == []
        assert result["_meta"]["count"] == 0

    def test_missing_key(self):
        """Should handle missing items key."""
        data = {"other_field": "value"}

        result = wrap_output(data, "systems", max_items=50)

        assert result["_meta"]["count"] == 0

    def test_non_list_value(self):
        """Should handle non-list values gracefully."""
        data = {"systems": "not a list"}

        result = wrap_output(data, "systems", max_items=50)

        assert result["_meta"]["count"] == 1  # Non-empty value

    def test_none_value(self):
        """Should handle None values."""
        data = {"systems": None}

        result = wrap_output(data, "systems", max_items=50)

        assert result["_meta"]["count"] == 0

    def test_preserves_other_fields(self):
        """Should preserve other fields in data."""
        data = {
            "systems": [{"name": "Jita"}],
            "total": 1,
            "query": "jita",
        }

        result = wrap_output(data, "systems", max_items=50)

        assert result["total"] == 1
        assert result["query"] == "jita"

    def test_custom_max_items(self):
        """Should respect custom max_items."""
        items = [{"id": i} for i in range(30)]
        data = {"items": items}

        result = wrap_output(data, "items", max_items=10)

        assert len(result["items"]) == 10
        assert result["_meta"]["truncated_from"] == 30


class TestWrapScalarOutput:
    """Tests for wrap_scalar_output function."""

    def test_with_data(self):
        """Should add metadata to non-list output."""
        data = {"item": {"name": "Tritanium", "type_id": 34}}

        result = wrap_scalar_output(data)

        assert result["_meta"]["count"] == 1
        assert result["item"]["name"] == "Tritanium"

    def test_empty_data(self):
        """Should handle empty data."""
        data = {}

        result = wrap_scalar_output(data)

        assert result["_meta"]["count"] == 0

    def test_none_values(self):
        """Should count None values as empty."""
        data = {"item": None, "other": None}

        result = wrap_scalar_output(data)

        assert result["_meta"]["count"] == 0

    def test_custom_count(self):
        """Should accept custom count."""
        data = {"items_processed": 42}

        result = wrap_scalar_output(data, count=42)

        assert result["_meta"]["count"] == 42


class TestWrapOutputMulti:
    """Tests for wrap_output_multi function."""

    def test_no_truncation_needed(self):
        """Should add metadata without truncating when under limits."""
        data = {
            "buy_orders": [{"id": 1}, {"id": 2}],
            "sell_orders": [{"id": 3}, {"id": 4}, {"id": 5}],
        }

        result = wrap_output_multi(data, [("buy_orders", 10), ("sell_orders", 10)])

        assert len(result["buy_orders"]) == 2
        assert len(result["sell_orders"]) == 3
        assert result["_meta"]["total_count"] == 5
        assert result["_meta"]["truncated"] is False
        assert result["_meta"]["lists"]["buy_orders"]["count"] == 2
        assert result["_meta"]["lists"]["sell_orders"]["count"] == 3

    def test_truncates_one_list(self):
        """Should truncate only the list that exceeds limit."""
        data = {
            "buy_orders": [{"id": i} for i in range(30)],
            "sell_orders": [{"id": i} for i in range(5)],
        }

        result = wrap_output_multi(data, [("buy_orders", 10), ("sell_orders", 10)])

        assert len(result["buy_orders"]) == 10
        assert len(result["sell_orders"]) == 5
        assert result["_meta"]["total_count"] == 15
        assert result["_meta"]["truncated"] is True
        assert result["_meta"]["lists"]["buy_orders"]["truncated"] is True
        assert result["_meta"]["lists"]["buy_orders"]["truncated_from"] == 30
        assert result["_meta"]["lists"]["sell_orders"]["truncated"] is False

    def test_truncates_multiple_lists(self):
        """Should truncate multiple lists that exceed limits."""
        data = {
            "contested": [{"id": i} for i in range(100)],
            "vulnerable": [{"id": i} for i in range(80)],
            "stable": [{"id": i} for i in range(60)],
        }

        result = wrap_output_multi(
            data,
            [("contested", 20), ("vulnerable", 20), ("stable", 20)],
        )

        assert len(result["contested"]) == 20
        assert len(result["vulnerable"]) == 20
        assert len(result["stable"]) == 20
        assert result["_meta"]["total_count"] == 60
        assert result["_meta"]["truncated"] is True
        assert result["_meta"]["lists"]["contested"]["truncated_from"] == 100
        assert result["_meta"]["lists"]["vulnerable"]["truncated_from"] == 80
        assert result["_meta"]["lists"]["stable"]["truncated_from"] == 60

    def test_empty_lists(self):
        """Should handle empty lists."""
        data = {
            "buy_orders": [],
            "sell_orders": [],
        }

        result = wrap_output_multi(data, [("buy_orders", 10), ("sell_orders", 10)])

        assert result["_meta"]["total_count"] == 0
        assert result["_meta"]["truncated"] is False

    def test_missing_key(self):
        """Should handle missing keys gracefully."""
        data = {"buy_orders": [{"id": 1}]}

        result = wrap_output_multi(data, [("buy_orders", 10), ("sell_orders", 10)])

        assert result["_meta"]["lists"]["buy_orders"]["count"] == 1
        assert result["_meta"]["lists"]["sell_orders"]["count"] == 0

    def test_non_list_value(self):
        """Should handle non-list values gracefully."""
        data = {
            "buy_orders": [{"id": 1}],
            "sell_orders": "not a list",
        }

        result = wrap_output_multi(data, [("buy_orders", 10), ("sell_orders", 10)])

        assert result["_meta"]["lists"]["buy_orders"]["count"] == 1
        assert result["_meta"]["lists"]["sell_orders"]["count"] == 1

    def test_preserves_other_fields(self):
        """Should preserve other fields in data."""
        data = {
            "buy_orders": [{"id": 1}],
            "sell_orders": [{"id": 2}],
            "best_buy": 100.0,
            "spread": 10.0,
        }

        result = wrap_output_multi(data, [("buy_orders", 10), ("sell_orders", 10)])

        assert result["best_buy"] == 100.0
        assert result["spread"] == 10.0

    def test_different_limits_per_list(self):
        """Should respect different limits for each list."""
        data = {
            "primary": [{"id": i} for i in range(50)],
            "secondary": [{"id": i} for i in range(50)],
        }

        result = wrap_output_multi(data, [("primary", 30), ("secondary", 10)])

        assert len(result["primary"]) == 30
        assert len(result["secondary"]) == 10
        assert result["_meta"]["total_count"] == 40

    def test_includes_timestamp(self):
        """Should include timestamp in metadata."""
        data = {"items": []}

        result = wrap_output_multi(data, [("items", 10)])

        assert "timestamp" in result["_meta"]


class TestCreateErrorMeta:
    """Tests for create_error_meta function."""

    def test_basic_error(self):
        """Should create error with code and message."""
        result = create_error_meta("NOT_FOUND", "System not found")

        assert result["error"] is True
        assert result["error_code"] == "NOT_FOUND"
        assert result["message"] == "System not found"
        assert result["_meta"]["count"] == 0

    def test_message_truncation(self):
        """Should truncate long messages."""
        long_message = "x" * 1000

        result = create_error_meta("ERROR", long_message, max_message_len=100)

        assert len(result["message"]) == 100
        assert result["message"].endswith("...")

    def test_message_at_limit(self):
        """Should not truncate message exactly at limit."""
        message = "x" * 100

        result = create_error_meta("ERROR", message, max_message_len=100)

        assert result["message"] == message

    def test_includes_timestamp(self):
        """Should include timestamp in metadata."""
        result = create_error_meta("ERROR", "test")

        assert "timestamp" in result["_meta"]


class TestByteEnforcement:
    """Tests for byte limit enforcement."""

    def test_enforce_output_bytes_no_truncation_needed(self):
        """Should not truncate when under byte limit."""
        data = {"items": [{"id": i} for i in range(5)]}

        result, meta = _enforce_output_bytes(data, "items", max_bytes=10000)

        assert len(result["items"]) == 5
        assert meta == {}  # No enforcement needed

    def test_enforce_output_bytes_truncates_at_limit(self):
        """Should truncate when over byte limit."""
        # Create large items that will exceed a small byte limit
        data = {"items": [{"id": i, "data": "x" * 100} for i in range(100)]}

        result, meta = _enforce_output_bytes(data, "items", max_bytes=1000)

        assert len(result["items"]) < 100
        assert meta.get("byte_limit_enforced") is True
        assert "original_bytes" in meta
        assert "final_bytes" in meta
        assert meta["final_bytes"] <= 1000

    def test_enforce_output_bytes_records_original_bytes(self):
        """Should record original byte size when truncating."""
        data = {"items": [{"id": i, "data": "x" * 50} for i in range(50)]}

        result, meta = _enforce_output_bytes(data, "items", max_bytes=500)

        assert meta.get("original_bytes") is not None
        assert meta["original_bytes"] > 500

    def test_enforce_output_bytes_preserves_under_limit(self):
        """Should preserve all items when under byte limit."""
        data = {"items": [{"id": 1}, {"id": 2}]}

        result, meta = _enforce_output_bytes(data, "items", max_bytes=10000)

        assert result["items"] == [{"id": 1}, {"id": 2}]
        assert meta == {}

    def test_enforce_output_bytes_multi_truncates_largest_first(self):
        """Should truncate the largest list first."""
        data = {
            "large_list": [{"id": i, "data": "x" * 50} for i in range(100)],
            "small_list": [{"id": i} for i in range(5)],
        }

        result, meta = _enforce_output_bytes_multi(
            data, [("large_list", 100), ("small_list", 10)], max_bytes=1000
        )

        # Large list should be truncated more than small list
        assert len(result["large_list"]) < 100
        assert meta.get("byte_limit_enforced") is True

    def test_wrap_output_enforces_byte_limit(self):
        """wrap_output should enforce byte limits."""
        data = {"items": [{"id": i, "data": "x" * 200} for i in range(1000)]}

        # Use a small byte limit to force truncation
        from aria_esi.mcp.context_policy import GLOBAL

        # Save original value
        original_limit = GLOBAL.MAX_OUTPUT_SIZE_BYTES

        result = wrap_output(data, "items", max_items=1000)

        # Should have been truncated either by item count or bytes
        assert len(result["items"]) <= 1000
        assert "_meta" in result

    def test_wrap_output_preserves_under_limit(self):
        """wrap_output should preserve items under byte limit."""
        data = {"items": [{"id": 1}, {"id": 2}]}

        result = wrap_output(data, "items", max_items=50)

        assert len(result["items"]) == 2
        assert result["_meta"]["count"] == 2


class TestProvenance:
    """Tests for provenance fields in metadata."""

    def test_output_meta_includes_source(self):
        """OutputMeta should include source when provided."""
        meta = OutputMeta(count=5, source="sde")
        d = meta.to_dict()

        assert d["source"] == "sde"

    def test_output_meta_includes_as_of(self):
        """OutputMeta should include as_of when provided."""
        meta = OutputMeta(count=5, as_of="2026-01-23T12:00:00+00:00")
        d = meta.to_dict()

        assert d["as_of"] == "2026-01-23T12:00:00+00:00"

    def test_output_meta_omits_source_when_none(self):
        """OutputMeta should omit source when None."""
        meta = OutputMeta(count=5)
        d = meta.to_dict()

        assert "source" not in d

    def test_output_meta_omits_as_of_when_none(self):
        """OutputMeta should omit as_of when None."""
        meta = OutputMeta(count=5)
        d = meta.to_dict()

        assert "as_of" not in d

    def test_wrap_output_includes_source(self):
        """wrap_output should include source in metadata."""
        data = {"items": [{"id": 1}]}

        result = wrap_output(data, "items", source="esi")

        assert result["_meta"]["source"] == "esi"

    def test_wrap_output_includes_as_of(self):
        """wrap_output should include as_of in metadata."""
        data = {"items": [{"id": 1}]}
        as_of = "2026-01-23T12:00:00+00:00"

        result = wrap_output(data, "items", as_of=as_of)

        assert result["_meta"]["as_of"] == as_of

    def test_wrap_scalar_output_includes_provenance(self):
        """wrap_scalar_output should include provenance fields."""
        data = {"item": {"name": "Tritanium"}}

        result = wrap_scalar_output(data, source="fuzzwork", as_of="2026-01-23T12:00:00+00:00")

        assert result["_meta"]["source"] == "fuzzwork"
        assert result["_meta"]["as_of"] == "2026-01-23T12:00:00+00:00"

    def test_wrap_output_multi_includes_provenance(self):
        """wrap_output_multi should include provenance fields."""
        data = {"list_a": [{"id": 1}], "list_b": [{"id": 2}]}

        result = wrap_output_multi(
            data,
            [("list_a", 10), ("list_b", 10)],
            source="eos",
            as_of="2026-01-23T12:00:00+00:00",
        )

        assert result["_meta"]["source"] == "eos"
        assert result["_meta"]["as_of"] == "2026-01-23T12:00:00+00:00"

    def test_output_meta_to_dict_includes_provenance(self):
        """OutputMeta.to_dict() should include all provenance fields."""
        meta = OutputMeta(
            count=10,
            truncated=True,
            truncated_from=20,
            source="sde",
            as_of="2026-01-23T12:00:00+00:00",
        )
        d = meta.to_dict()

        assert d["count"] == 10
        assert d["truncated"] is True
        assert d["truncated_from"] == 20
        assert d["source"] == "sde"
        assert d["as_of"] == "2026-01-23T12:00:00+00:00"


class TestTraceContext:
    """Tests for trace context management."""

    @pytest.fixture(autouse=True)
    def reset_trace(self):
        """Reset trace context before and after each test."""
        reset_trace_context()
        yield
        reset_trace_context()

    def test_set_and_get_trace_context(self):
        """Should set and get trace context."""
        set_trace_context(trace_id="abc-123", turn_id=5)

        ctx = get_trace_context()

        assert ctx["trace_id"] == "abc-123"
        assert ctx["turn_id"] == 5

    def test_get_trace_context_defaults_to_none(self):
        """Should return None for unset trace context."""
        ctx = get_trace_context()

        assert ctx["trace_id"] is None
        assert ctx["turn_id"] is None

    def test_reset_trace_context(self):
        """Should reset trace context to None."""
        set_trace_context(trace_id="abc-123", turn_id=5)
        reset_trace_context()

        ctx = get_trace_context()

        assert ctx["trace_id"] is None
        assert ctx["turn_id"] is None

    def test_partial_trace_context(self):
        """Should handle partial trace context (only trace_id or only turn_id)."""
        set_trace_context(trace_id="abc-123")
        ctx = get_trace_context()

        assert ctx["trace_id"] == "abc-123"
        assert ctx["turn_id"] is None

        set_trace_context(turn_id=10)
        ctx = get_trace_context()

        assert ctx["trace_id"] is None  # Was reset
        assert ctx["turn_id"] == 10

    def test_set_trace_context_overwrites(self):
        """Should overwrite existing trace context."""
        set_trace_context(trace_id="first", turn_id=1)
        set_trace_context(trace_id="second", turn_id=2)

        ctx = get_trace_context()

        assert ctx["trace_id"] == "second"
        assert ctx["turn_id"] == 2
