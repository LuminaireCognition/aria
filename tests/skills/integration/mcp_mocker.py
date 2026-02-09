"""
MCP Mock Server and Response Injection.

Provides utilities for mocking MCP dispatcher calls during integration tests.
This enables Tier 1 testing where we validate the skill's MCP call contract
without actually invoking external services.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import yaml


@dataclass
class MockMCPServer:
    """
    Mock MCP server that returns fixture data for tool calls.

    Usage:
        server = MockMCPServer()
        server.load_fixture("path/to/fixture.yaml")

        # Or load directly from dict
        server.set_response("sde", "blueprint_info", {...})

        # Get mock response
        response = server.get_response("sde", "blueprint_info")
    """

    responses: dict[tuple[str, str], Any] = field(default_factory=dict)
    call_log: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def load_fixture(self, fixture_path: Path | str) -> None:
        """
        Load mock responses from a fixture file.

        The fixture should have a 'mock_responses' section with keys like:
        - sde_blueprint_info: Response for sde(action="blueprint_info")
        - market_prices: Response for market(action="prices")
        - universe_route: Response for universe(action="route")

        Args:
            fixture_path: Path to the YAML fixture file
        """
        with open(fixture_path) as f:
            fixture = yaml.safe_load(f)

        mock_responses = fixture.get("mock_responses", {})
        for key, response in mock_responses.items():
            # Parse key format: dispatcher_action (e.g., sde_blueprint_info)
            parts = key.split("_", 1)
            if len(parts) == 2:
                dispatcher, action = parts
                self.set_response(dispatcher, action, response)

    def set_response(self, dispatcher: str, action: str, response: Any) -> None:
        """
        Configure a response for a specific dispatcher/action combination.

        Args:
            dispatcher: The MCP dispatcher name (sde, market, universe, etc.)
            action: The action parameter value
            response: The response data to return
        """
        self.responses[(dispatcher, action)] = response

    def get_response(self, dispatcher: str, action: str) -> Any:
        """
        Get the configured response for a dispatcher/action.

        Args:
            dispatcher: The MCP dispatcher name
            action: The action parameter value

        Returns:
            The configured response, or None if not set
        """
        return self.responses.get((dispatcher, action))

    def mock_call(self, dispatcher: str, action: str, **kwargs: Any) -> Any:
        """
        Simulate an MCP dispatcher call, logging it and returning mock response.

        Args:
            dispatcher: The MCP dispatcher name
            action: The action parameter value
            **kwargs: Additional parameters passed to the dispatcher

        Returns:
            The configured mock response
        """
        self.call_log.append((dispatcher, action, kwargs))
        return copy.deepcopy(self.responses.get((dispatcher, action), {}))

    def was_called(self, dispatcher: str, action: str | None = None) -> bool:
        """
        Check if a dispatcher (and optionally action) was called.

        Args:
            dispatcher: The dispatcher name to check
            action: Optional action to check

        Returns:
            True if the call was made
        """
        for d, a, _ in self.call_log:
            if d == dispatcher and (action is None or a == action):
                return True
        return False

    def called_with(self, dispatcher: str, action: str, **expected_kwargs: Any) -> bool:
        """
        Check if a specific call was made with expected parameters.

        Args:
            dispatcher: The dispatcher name
            action: The action value
            **expected_kwargs: Parameters to match

        Returns:
            True if a matching call was found
        """
        for d, a, kwargs in self.call_log:
            if d == dispatcher and a == action:
                match = all(kwargs.get(k) == v for k, v in expected_kwargs.items())
                if match:
                    return True
        return False

    def get_calls(
        self, dispatcher: str, action: str | None = None
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """
        Get all logged calls matching dispatcher and optionally action.

        Args:
            dispatcher: The dispatcher name
            action: Optional action to filter by

        Returns:
            List of (dispatcher, action, kwargs) tuples
        """
        return [
            (d, a, k)
            for d, a, k in self.call_log
            if d == dispatcher and (action is None or a == action)
        ]

    def reset(self) -> None:
        """Clear all logged calls."""
        self.call_log.clear()


def _create_mock_dispatcher(
    mock_server: MockMCPServer, dispatcher_name: str
) -> Callable[..., Any]:
    """
    Create a mock dispatcher function that logs calls to the mock server.

    Args:
        mock_server: The MockMCPServer to log calls to
        dispatcher_name: Name of the dispatcher (sde, market, etc.)

    Returns:
        A function that simulates the dispatcher
    """

    def mock_dispatcher(action: str, **kwargs: Any) -> Any:
        return mock_server.mock_call(dispatcher_name, action, **kwargs)

    return mock_dispatcher


@contextmanager
def inject_mock_responses(
    mock_server: MockMCPServer,
    dispatchers: list[str] | None = None,
) -> Iterator[MockMCPServer]:
    """
    Context manager that patches MCP dispatchers with mock responses.

    Usage:
        mock_server = MockMCPServer()
        mock_server.set_response("sde", "blueprint_info", {...})

        with inject_mock_responses(mock_server) as server:
            # Code that calls MCP dispatchers
            result = call_skill_that_uses_sde()

        assert server.was_called("sde", "blueprint_info")

    Args:
        mock_server: MockMCPServer with configured responses
        dispatchers: List of dispatcher names to patch. Defaults to all.

    Yields:
        The mock server for call verification
    """
    if dispatchers is None:
        dispatchers = ["sde", "market", "universe", "skills", "fitting", "status"]

    # Build patch targets - these are the dispatcher entry points
    patches = []
    for dispatcher in dispatchers:
        # Each dispatcher has a main entry function we can mock
        mock_func = _create_mock_dispatcher(mock_server, dispatcher)
        mock_obj = MagicMock(side_effect=mock_func)

        # Patch the dispatcher entry point
        patch_target = f"aria_esi.mcp.dispatchers.{dispatcher}.{dispatcher}"
        patches.append(patch(patch_target, mock_obj))

    try:
        # Start all patches
        for p in patches:
            try:
                p.start()
            except (ModuleNotFoundError, AttributeError):
                # Dispatcher module may not exist or have different structure
                pass

        yield mock_server
    finally:
        # Stop all patches
        for p in patches:
            try:
                p.stop()
            except (RuntimeError, AttributeError):
                pass


def load_fixture_with_mocks(fixture_path: Path | str) -> tuple[dict[str, Any], MockMCPServer]:
    """
    Load a fixture file and create a MockMCPServer with its mock_responses.

    Args:
        fixture_path: Path to the YAML fixture file

    Returns:
        Tuple of (fixture_data, mock_server)
    """
    with open(fixture_path) as f:
        fixture = yaml.safe_load(f)

    mock_server = MockMCPServer()
    mock_server.load_fixture(fixture_path)

    return fixture, mock_server
