"""
Tests for Fitting Status MCP Tool.

Tests EOS status reporting and error fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.mcp.fitting.tools_status import register_status_tools


@dataclass
class MockEOSDataStatus:
    is_valid: bool = True
    data_path: Path = Path("/fake/eos-data")
    version: str | None = "2548611"
    fsd_built_files: list[str] = field(default_factory=lambda: ["types.json"])
    fsd_lite_files: list[str] = field(default_factory=list)
    phobos_files: list[str] = field(default_factory=lambda: ["metadata.json"])
    missing_files: list[str] = field(default_factory=list)
    total_records: int = 45000
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "data_path": str(self.data_path),
            "version": self.version,
            "files": {
                "fsd_built": self.fsd_built_files,
                "fsd_lite": self.fsd_lite_files,
                "phobos": self.phobos_files,
            },
            "missing_files": self.missing_files,
            "total_records": self.total_records,
            "error_message": self.error_message,
        }


@pytest.fixture
def status_tool():
    """Register status tools and return the inner async function."""
    server = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    server.tool = tool_decorator
    register_status_tools(server)
    return tools["fitting_status"]


class TestFittingStatus:
    @pytest.mark.anyio
    async def test_valid_status(self, status_tool) -> None:
        """Returns status dict on success."""
        mock_status = MockEOSDataStatus()
        mock_manager = MagicMock()
        mock_manager.validate.return_value = mock_status

        with patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager):
            result = await status_tool()

        assert result["is_valid"] is True
        assert result["version"] == "2548611"
        assert result["total_records"] == 45000

    @pytest.mark.anyio
    async def test_invalid_status(self, status_tool) -> None:
        """Returns status dict with is_valid=False when data is missing."""
        mock_status = MockEOSDataStatus(
            is_valid=False,
            missing_files=["types.json"],
            error_message="Missing required files",
        )
        mock_manager = MagicMock()
        mock_manager.validate.return_value = mock_status

        with patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager):
            result = await status_tool()

        assert result["is_valid"] is False
        assert "types.json" in result["missing_files"]

    @pytest.mark.anyio
    async def test_exception_fallback(self, status_tool) -> None:
        """Returns fallback dict with is_valid=False on exception."""
        with patch(
            "aria_esi.fitting.get_eos_data_manager",
            side_effect=RuntimeError("Import failed"),
        ):
            result = await status_tool()

        assert result["is_valid"] is False
        assert "Import failed" in result["error_message"]
        assert "hint" in result

    @pytest.mark.anyio
    async def test_status_calls_validate(self, status_tool) -> None:
        """Calls data_manager.validate() not ensure_valid()."""
        mock_status = MockEOSDataStatus()
        mock_manager = MagicMock()
        mock_manager.validate.return_value = mock_status

        with patch("aria_esi.fitting.get_eos_data_manager", return_value=mock_manager):
            await status_tool()

        mock_manager.validate.assert_called_once()
