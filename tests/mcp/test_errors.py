"""
Tests for MCP Error Classes.

STP-004: MCP Server Core Tests
"""


from aria_esi.mcp.errors import (
    InsufficientBordersError,
    InvalidParameterError,
    RouteNotFoundError,
    SystemNotFoundError,
    UniverseError,
)

# =============================================================================
# UniverseError Base Class Tests
# =============================================================================


class TestUniverseError:
    """Test UniverseError base class."""

    def test_basic_construction(self):
        """UniverseError can be raised with message."""
        error = UniverseError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_default_code(self):
        """UniverseError has default code."""
        error = UniverseError("Something went wrong")
        assert error.code == "UNIVERSE_ERROR"

    def test_to_mcp_error_format(self):
        """to_mcp_error returns MCP-compliant format."""
        error = UniverseError("Something went wrong")
        mcp_error = error.to_mcp_error()

        assert "error" in mcp_error
        assert mcp_error["error"]["code"] == "UNIVERSE_ERROR"
        assert mcp_error["error"]["message"] == "Something went wrong"
        assert mcp_error["error"]["data"] == {}

    def test_inherits_from_exception(self):
        """UniverseError is an Exception subclass."""
        assert issubclass(UniverseError, Exception)


# =============================================================================
# SystemNotFoundError Tests
# =============================================================================


class TestSystemNotFoundError:
    """Test SystemNotFoundError exception."""

    def test_basic_construction(self):
        """SystemNotFoundError constructs with name."""
        error = SystemNotFoundError("Juta")
        assert error.name == "Juta"
        assert error.suggestions == []
        assert str(error) == "Unknown system: Juta"

    def test_with_suggestions(self):
        """SystemNotFoundError includes suggestions."""
        error = SystemNotFoundError("Juta", suggestions=["Jita", "Jatate"])
        assert error.name == "Juta"
        assert error.suggestions == ["Jita", "Jatate"]
        # Suggestions appear in error message
        assert "Did you mean: Jita, Jatate?" in str(error)

    def test_mcp_error_code(self):
        """SystemNotFoundError has correct MCP code."""
        error = SystemNotFoundError("Juta")
        assert error.code == "SYSTEM_NOT_FOUND"

    def test_mcp_error_format(self):
        """SystemNotFoundError serializes to MCP format."""
        error = SystemNotFoundError("Juta", suggestions=["Jita", "Jatate"])
        mcp_error = error.to_mcp_error()

        assert mcp_error["error"]["code"] == "SYSTEM_NOT_FOUND"
        assert "Juta" in mcp_error["error"]["message"]
        assert mcp_error["error"]["data"]["suggestions"] == ["Jita", "Jatate"]

    def test_empty_suggestions_in_data(self):
        """Empty suggestions still present in data."""
        error = SystemNotFoundError("Unknown")
        mcp_error = error.to_mcp_error()

        assert mcp_error["error"]["data"]["suggestions"] == []

    def test_inherits_from_universe_error(self):
        """SystemNotFoundError is UniverseError subclass."""
        assert issubclass(SystemNotFoundError, UniverseError)


# =============================================================================
# RouteNotFoundError Tests
# =============================================================================


class TestRouteNotFoundError:
    """Test RouteNotFoundError exception."""

    def test_basic_construction(self):
        """RouteNotFoundError constructs with origin and destination."""
        error = RouteNotFoundError("System A", "System B")
        assert error.origin == "System A"
        assert error.destination == "System B"
        assert error.reason is None
        assert str(error) == "No route from System A to System B"

    def test_with_reason(self):
        """RouteNotFoundError includes reason in message."""
        error = RouteNotFoundError("System A", "System B", reason="No gate connection")
        assert error.reason == "No gate connection"
        assert str(error) == "No route from System A to System B: No gate connection"

    def test_mcp_error_code(self):
        """RouteNotFoundError has correct MCP code."""
        error = RouteNotFoundError("A", "B")
        assert error.code == "ROUTE_NOT_FOUND"

    def test_mcp_error_format(self):
        """RouteNotFoundError serializes to MCP format."""
        error = RouteNotFoundError("System A", "System B", reason="No gate connection")
        mcp_error = error.to_mcp_error()

        assert mcp_error["error"]["code"] == "ROUTE_NOT_FOUND"
        assert mcp_error["error"]["data"]["origin"] == "System A"
        assert mcp_error["error"]["data"]["destination"] == "System B"
        assert mcp_error["error"]["data"]["reason"] == "No gate connection"

    def test_none_reason_in_data(self):
        """None reason is included in data."""
        error = RouteNotFoundError("A", "B")
        mcp_error = error.to_mcp_error()

        assert mcp_error["error"]["data"]["reason"] is None

    def test_inherits_from_universe_error(self):
        """RouteNotFoundError is UniverseError subclass."""
        assert issubclass(RouteNotFoundError, UniverseError)


# =============================================================================
# InvalidParameterError Tests
# =============================================================================


class TestInvalidParameterError:
    """Test InvalidParameterError exception."""

    def test_basic_construction(self):
        """InvalidParameterError constructs with param, value, reason."""
        error = InvalidParameterError("mode", "fastest", "must be one of: shortest, safe, unsafe")
        assert error.param == "mode"
        assert error.value == "fastest"
        assert error.reason == "must be one of: shortest, safe, unsafe"
        assert str(error) == "Invalid mode: must be one of: shortest, safe, unsafe"

    def test_mcp_error_code(self):
        """InvalidParameterError has correct MCP code."""
        error = InvalidParameterError("x", "y", "z")
        assert error.code == "INVALID_PARAMETER"

    def test_mcp_error_format(self):
        """InvalidParameterError serializes to MCP format."""
        error = InvalidParameterError("limit", -5, "must be positive")
        mcp_error = error.to_mcp_error()

        assert mcp_error["error"]["code"] == "INVALID_PARAMETER"
        assert mcp_error["error"]["data"]["parameter"] == "limit"
        assert mcp_error["error"]["data"]["value"] == "-5"
        assert mcp_error["error"]["data"]["reason"] == "must be positive"

    def test_value_stringified(self):
        """Value is converted to string in error data."""
        error = InvalidParameterError("count", 42, "too many")
        mcp_error = error.to_mcp_error()

        assert mcp_error["error"]["data"]["value"] == "42"

    def test_none_value_stringified(self):
        """None value is converted to string."""
        error = InvalidParameterError("origin", None, "required")
        mcp_error = error.to_mcp_error()

        assert mcp_error["error"]["data"]["value"] == "None"

    def test_inherits_from_universe_error(self):
        """InvalidParameterError is UniverseError subclass."""
        assert issubclass(InvalidParameterError, UniverseError)


# =============================================================================
# InsufficientBordersError Tests
# =============================================================================


class TestInsufficientBordersError:
    """Test InsufficientBordersError exception."""

    def test_basic_construction(self):
        """InsufficientBordersError constructs with found, required, search_radius."""
        error = InsufficientBordersError(found=2, required=5, search_radius=10)
        assert error.found == 2
        assert error.required == 5
        assert error.search_radius == 10
        assert "2" in str(error)
        assert "5" in str(error)
        assert "10" in str(error)

    def test_default_suggestion(self):
        """InsufficientBordersError has default suggestion."""
        error = InsufficientBordersError(found=2, required=5, search_radius=10)
        assert "target_jumps" in error.suggestion
        assert "min_borders" in error.suggestion
        assert "security_filter" in error.suggestion

    def test_custom_suggestion(self):
        """InsufficientBordersError accepts custom suggestion."""
        error = InsufficientBordersError(
            found=1, required=3, search_radius=5, suggestion="Try a different origin"
        )
        assert error.suggestion == "Try a different origin"

    def test_mcp_error_code(self):
        """InsufficientBordersError has correct MCP code."""
        error = InsufficientBordersError(found=2, required=5, search_radius=10)
        assert error.code == "INSUFFICIENT_BORDERS"

    def test_mcp_error_format(self):
        """InsufficientBordersError serializes to MCP format."""
        error = InsufficientBordersError(found=2, required=5, search_radius=10)
        mcp_error = error.to_mcp_error()

        assert mcp_error["error"]["code"] == "INSUFFICIENT_BORDERS"
        assert mcp_error["error"]["data"]["found"] == 2
        assert mcp_error["error"]["data"]["required"] == 5
        assert mcp_error["error"]["data"]["search_radius"] == 10
        assert "suggestion" in mcp_error["error"]["data"]

    def test_inherits_from_universe_error(self):
        """InsufficientBordersError is UniverseError subclass."""
        assert issubclass(InsufficientBordersError, UniverseError)


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Test that all error classes are exported correctly."""

    def test_all_errors_exported(self):
        """All error classes are exported from mcp module."""
        from aria_esi.mcp import (
            InsufficientBordersError,
            InvalidParameterError,
            RouteNotFoundError,
            SystemNotFoundError,
            UniverseError,
        )

        # Verify imports work
        assert UniverseError is not None
        assert SystemNotFoundError is not None
        assert RouteNotFoundError is not None
        assert InvalidParameterError is not None
        assert InsufficientBordersError is not None

    def test_can_catch_with_base_class(self):
        """All error types can be caught as UniverseError."""
        errors = [
            SystemNotFoundError("test"),
            RouteNotFoundError("a", "b"),
            InvalidParameterError("p", "v", "r"),
            InsufficientBordersError(1, 2, 3),
        ]

        for error in errors:
            try:
                raise error
            except UniverseError as e:
                assert e is error
