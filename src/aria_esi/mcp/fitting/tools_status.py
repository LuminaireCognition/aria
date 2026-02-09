"""
MCP Tool: fitting_status

Reports the status of the EOS fitting engine and data files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.logging import get_logger

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger(__name__)


def register_status_tools(server: FastMCP) -> None:
    """Register fitting status tools with MCP server."""

    @server.tool()
    async def fitting_status() -> dict:
        """
        Get the status of the EOS fitting calculation engine.

        Returns information about:
        - Whether EOS data is available and valid
        - Data version (EVE client build number)
        - Available data files
        - Any missing required files

        Returns:
            Dictionary with EOS status information:
            - is_valid: Whether the fitting engine can be used
            - data_path: Path to EOS data directory
            - version: EVE client build version of the data
            - files: Lists of available data files by category
            - missing_files: List of any missing required files
            - total_records: Approximate number of type records
            - error_message: Error description if not valid

        Example response:
            {
                "is_valid": true,
                "data_path": "/home/user/.aria/eos-data",
                "version": "2548611",
                "files": {
                    "fsd_built": ["types.json", "dogmaeffects.json", ...],
                    "fsd_lite": ["fighterabilitiesbytype.json", ...],
                    "phobos": ["metadata.json"]
                },
                "missing_files": [],
                "total_records": 45678,
                "error_message": null
            }
        """
        from aria_esi.fitting import get_eos_data_manager

        try:
            data_manager = get_eos_data_manager()
            status = data_manager.validate()
            return status.to_dict()
        except Exception as e:
            logger.exception("Error checking fitting status")
            return {
                "is_valid": False,
                "error_message": str(e),
                "hint": "Run 'uv run aria-esi eos-seed' to download EOS data",
            }
