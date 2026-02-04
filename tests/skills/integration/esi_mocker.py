"""
ESI Mock Server and Response Injection.

Provides utilities for mocking ESI (EVE Swagger Interface) API calls during
integration tests. This enables Tier 1 testing of ESI-dependent skills
without requiring live API access or OAuth tokens.

Follows the same patterns as mcp_mocker.py for consistency.

Usage:
    from tests.skills.integration.esi_mocker import MockESIServer, inject_esi_mocks

    # Create mock server with fixture responses
    server = MockESIServer()
    server.load_fixture("path/to/fixture.yaml")

    # Or set responses directly
    server.set_response("characters/{character_id}/skills", {
        "skills": [...],
        "total_sp": 5000000
    })

    # Use context manager to inject mocks
    with inject_esi_mocks(server):
        # Code that calls ESI endpoints
        result = my_esi_function()

    # Verify calls
    assert server.was_called("characters/{character_id}/skills")
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import yaml

# Common ESI endpoint patterns and their path template forms
ESI_ENDPOINT_PATTERNS = {
    # Character endpoints
    r"characters/\d+/skills": "characters/{character_id}/skills",
    r"characters/\d+/skillqueue": "characters/{character_id}/skillqueue",
    r"characters/\d+/clones": "characters/{character_id}/clones",
    r"characters/\d+/implants": "characters/{character_id}/implants",
    r"characters/\d+/wallet": "characters/{character_id}/wallet",
    r"characters/\d+/wallet/journal": "characters/{character_id}/wallet/journal",
    r"characters/\d+/assets": "characters/{character_id}/assets",
    r"characters/\d+/standings": "characters/{character_id}/standings",
    r"characters/\d+/location": "characters/{character_id}/location",
    r"characters/\d+/ship": "characters/{character_id}/ship",
    r"characters/\d+/contracts": "characters/{character_id}/contracts",
    r"characters/\d+/orders": "characters/{character_id}/orders",
    r"characters/\d+/fittings": "characters/{character_id}/fittings",
    r"characters/\d+/mail": "characters/{character_id}/mail",
    r"characters/\d+/mining": "characters/{character_id}/mining",
    r"characters/\d+/industry/jobs": "characters/{character_id}/industry/jobs",
    r"characters/\d+/loyalty/points": "characters/{character_id}/loyalty/points",
    r"characters/\d+/agents_research": "characters/{character_id}/agents_research",
    r"characters/\d+/blueprints": "characters/{character_id}/blueprints",
    r"characters/\d+/killmails/recent": "characters/{character_id}/killmails/recent",

    # Corporation endpoints
    r"corporations/\d+": "corporations/{corporation_id}",
    r"corporations/\d+/assets": "corporations/{corporation_id}/assets",
    r"corporations/\d+/wallets": "corporations/{corporation_id}/wallets",
    r"corporations/\d+/industry/jobs": "corporations/{corporation_id}/industry/jobs",
    r"corporations/\d+/blueprints": "corporations/{corporation_id}/blueprints",

    # Universe endpoints
    r"universe/systems/\d+": "universe/systems/{system_id}",
    r"universe/types/\d+": "universe/types/{type_id}",
    r"universe/regions/\d+": "universe/regions/{region_id}",

    # Market endpoints
    r"markets/\d+/orders": "markets/{region_id}/orders",
    r"markets/prices": "markets/prices",

    # Killmail endpoints
    r"killmails/\d+/\w+": "killmails/{killmail_id}/{killmail_hash}",
}


def normalize_endpoint(endpoint: str) -> str:
    """
    Normalize an ESI endpoint URL to its template form.

    Args:
        endpoint: Raw endpoint like "characters/12345/skills"

    Returns:
        Template form like "characters/{character_id}/skills"
    """
    for pattern, template in ESI_ENDPOINT_PATTERNS.items():
        if re.match(pattern, endpoint):
            return template
    return endpoint


@dataclass
class ESICall:
    """Record of a single ESI API call."""

    endpoint: str
    method: str
    params: dict[str, Any]
    character_id: int | None = None


@dataclass
class MockESIServer:
    """
    Mock ESI server that returns fixture data for API calls.

    Usage:
        server = MockESIServer()
        server.load_fixture("path/to/fixture.yaml")

        # Or load directly from dict
        server.set_response("characters/{character_id}/skills", {...})

        # Get mock response
        response = server.get_response("characters/12345/skills")
    """

    responses: dict[str, Any] = field(default_factory=dict)
    call_log: list[ESICall] = field(default_factory=list)

    def load_fixture(self, fixture_path: Path | str) -> None:
        """
        Load mock responses from a fixture file.

        The fixture should have an 'esi_responses' section with keys matching
        ESI endpoint templates:
        - skillqueue: Response for characters/{character_id}/skillqueue
        - skills: Response for characters/{character_id}/skills
        - assets: Response for characters/{character_id}/assets

        Args:
            fixture_path: Path to the YAML fixture file
        """
        with open(fixture_path) as f:
            fixture = yaml.safe_load(f)

        esi_responses = fixture.get("esi_responses", {})
        for key, response in esi_responses.items():
            # Map short keys to full endpoint templates
            endpoint = self._map_short_key_to_endpoint(key)
            self.set_response(endpoint, response)

    def _map_short_key_to_endpoint(self, key: str) -> str:
        """Map fixture short keys to full endpoint templates."""
        key_mappings = {
            "skills": "characters/{character_id}/skills",
            "skillqueue": "characters/{character_id}/skillqueue",
            "clones": "characters/{character_id}/clones",
            "implants": "characters/{character_id}/implants",
            "wallet": "characters/{character_id}/wallet",
            "wallet_journal": "characters/{character_id}/wallet/journal",
            "assets": "characters/{character_id}/assets",
            "standings": "characters/{character_id}/standings",
            "location": "characters/{character_id}/location",
            "ship": "characters/{character_id}/ship",
            "contracts": "characters/{character_id}/contracts",
            "orders": "characters/{character_id}/orders",
            "fittings": "characters/{character_id}/fittings",
            "mail": "characters/{character_id}/mail",
            "mining": "characters/{character_id}/mining",
            "industry_jobs": "characters/{character_id}/industry/jobs",
            "loyalty_points": "characters/{character_id}/loyalty/points",
            "agents_research": "characters/{character_id}/agents_research",
            "blueprints": "characters/{character_id}/blueprints",
            "killmails": "characters/{character_id}/killmails/recent",
            "corp_assets": "corporations/{corporation_id}/assets",
            "corp_wallets": "corporations/{corporation_id}/wallets",
            "corp_jobs": "corporations/{corporation_id}/industry/jobs",
        }
        return key_mappings.get(key, key)

    def set_response(self, endpoint: str, response: Any) -> None:
        """
        Configure a response for a specific endpoint.

        Args:
            endpoint: The endpoint template (e.g., "characters/{character_id}/skills")
            response: The response data to return
        """
        # Normalize the endpoint
        normalized = normalize_endpoint(endpoint)
        self.responses[normalized] = response

    def get_response(self, endpoint: str) -> Any:
        """
        Get the configured response for an endpoint.

        Args:
            endpoint: The endpoint (raw or template form)

        Returns:
            The configured response, or None if not set
        """
        normalized = normalize_endpoint(endpoint)
        return self.responses.get(normalized)

    def mock_call(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        character_id: int | None = None,
    ) -> Any:
        """
        Simulate an ESI API call, logging it and returning mock response.

        Args:
            endpoint: The endpoint being called
            method: HTTP method (GET, POST, etc.)
            params: Query parameters or body
            character_id: Character ID if applicable

        Returns:
            The configured mock response
        """
        self.call_log.append(
            ESICall(
                endpoint=endpoint,
                method=method,
                params=params or {},
                character_id=character_id,
            )
        )
        normalized = normalize_endpoint(endpoint)
        return copy.deepcopy(self.responses.get(normalized, {}))

    def was_called(self, endpoint: str | None = None) -> bool:
        """
        Check if an endpoint (or any endpoint) was called.

        Args:
            endpoint: Optional endpoint to check (normalized automatically)

        Returns:
            True if the call was made
        """
        if endpoint is None:
            return len(self.call_log) > 0

        normalized = normalize_endpoint(endpoint)
        for call in self.call_log:
            if normalize_endpoint(call.endpoint) == normalized:
                return True
        return False

    def called_with(self, endpoint: str, **expected_params: Any) -> bool:
        """
        Check if a specific call was made with expected parameters.

        Args:
            endpoint: The endpoint to check
            **expected_params: Parameters to match

        Returns:
            True if a matching call was found
        """
        normalized = normalize_endpoint(endpoint)
        for call in self.call_log:
            if normalize_endpoint(call.endpoint) == normalized:
                if all(call.params.get(k) == v for k, v in expected_params.items()):
                    return True
        return False

    def get_calls(self, endpoint: str | None = None) -> list[ESICall]:
        """
        Get all logged calls, optionally filtered by endpoint.

        Args:
            endpoint: Optional endpoint to filter by

        Returns:
            List of ESICall records
        """
        if endpoint is None:
            return list(self.call_log)

        normalized = normalize_endpoint(endpoint)
        return [
            c for c in self.call_log
            if normalize_endpoint(c.endpoint) == normalized
        ]

    def reset(self) -> None:
        """Clear all logged calls."""
        self.call_log.clear()


def _create_mock_esi_client(mock_server: MockESIServer) -> MagicMock:
    """
    Create a mock ESI client that logs calls to the mock server.

    Args:
        mock_server: The MockESIServer to log calls to

    Returns:
        A MagicMock configured to simulate ESI client behavior
    """
    mock_client = MagicMock()

    def mock_request(method: str, endpoint: str, **kwargs):
        """Simulate an ESI request."""
        params = kwargs.get("params", {})
        character_id = kwargs.get("character_id")
        return mock_server.mock_call(
            endpoint=endpoint,
            method=method,
            params=params,
            character_id=character_id,
        )

    mock_client.get = lambda endpoint, **kwargs: mock_request("GET", endpoint, **kwargs)
    mock_client.post = lambda endpoint, **kwargs: mock_request("POST", endpoint, **kwargs)
    mock_client.request = mock_request

    return mock_client


@contextmanager
def inject_esi_mocks(
    mock_server: MockESIServer,
    patch_targets: list[str] | None = None,
) -> Iterator[MockESIServer]:
    """
    Context manager that patches ESI client with mock responses.

    Usage:
        mock_server = MockESIServer()
        mock_server.set_response("characters/{character_id}/skills", {...})

        with inject_esi_mocks(mock_server) as server:
            # Code that calls ESI endpoints
            result = skill_that_uses_esi()

        assert server.was_called("characters/{character_id}/skills")

    Args:
        mock_server: MockESIServer with configured responses
        patch_targets: List of module paths to patch. Defaults to common ESI client locations.

    Yields:
        The mock server for call verification
    """
    if patch_targets is None:
        # Common locations where ESI clients might be imported
        patch_targets = [
            "aria_esi.esi.client.ESIClient",
            "aria_esi.esi.ESIClient",
        ]

    mock_client = _create_mock_esi_client(mock_server)
    patches = []

    for target in patch_targets:
        try:
            p = patch(target, return_value=mock_client)
            patches.append(p)
        except (ModuleNotFoundError, AttributeError):
            # Target may not exist
            pass

    try:
        # Start all patches
        for p in patches:
            try:
                p.start()
            except (ModuleNotFoundError, AttributeError):
                pass

        yield mock_server
    finally:
        # Stop all patches
        for p in patches:
            try:
                p.stop()
            except (RuntimeError, AttributeError):
                pass


def load_fixture_with_esi_mocks(
    fixture_path: Path | str,
) -> tuple[dict[str, Any], MockESIServer]:
    """
    Load a fixture file and create a MockESIServer with its esi_responses.

    Args:
        fixture_path: Path to the YAML fixture file

    Returns:
        Tuple of (fixture_data, mock_server)
    """
    with open(fixture_path) as f:
        fixture = yaml.safe_load(f)

    mock_server = MockESIServer()
    mock_server.load_fixture(fixture_path)

    return fixture, mock_server


# =============================================================================
# Common ESI Response Templates
# =============================================================================


def make_skills_response(
    skills: list[dict[str, Any]] | None = None,
    total_sp: int = 5000000,
    unallocated_sp: int = 0,
) -> dict[str, Any]:
    """
    Create a mock skills response.

    Args:
        skills: List of skill entries, or None for default
        total_sp: Total skill points
        unallocated_sp: Unallocated skill points

    Returns:
        Mock skills API response
    """
    if skills is None:
        skills = [
            {"skill_id": 3436, "trained_skill_level": 5, "active_skill_level": 5, "skillpoints_in_skill": 256000},
            {"skill_id": 33699, "trained_skill_level": 4, "active_skill_level": 4, "skillpoints_in_skill": 45255},
        ]

    return {
        "skills": skills,
        "total_sp": total_sp,
        "unallocated_sp": unallocated_sp,
    }


def make_skillqueue_response(
    queue: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Create a mock skill queue response.

    Args:
        queue: List of queue entries, or None for default

    Returns:
        Mock skillqueue API response
    """
    if queue is None:
        queue = [
            {
                "skill_id": 3436,
                "finished_level": 5,
                "queue_position": 0,
                "start_date": "2026-01-15T10:00:00Z",
                "finish_date": "2026-01-16T20:45:00Z",
                "training_start_sp": 200000,
                "level_start_sp": 0,
                "level_end_sp": 256000,
            }
        ]

    return queue


def make_assets_response(
    assets: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Create a mock assets response.

    Args:
        assets: List of asset entries, or None for default

    Returns:
        Mock assets API response
    """
    if assets is None:
        assets = [
            {
                "item_id": 1000000001,
                "type_id": 32880,  # Venture
                "location_id": 60003760,  # Jita 4-4
                "location_type": "station",
                "quantity": 1,
                "is_singleton": True,
            },
            {
                "item_id": 1000000002,
                "type_id": 34,  # Tritanium
                "location_id": 60003760,
                "location_type": "station",
                "quantity": 100000,
                "is_singleton": False,
            },
        ]

    return assets


def make_standings_response(
    standings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Create a mock standings response.

    Args:
        standings: List of standing entries, or None for default

    Returns:
        Mock standings API response
    """
    if standings is None:
        standings = [
            {"from_id": 500004, "from_type": "faction", "standing": 5.5},  # Gallente
            {"from_id": 500001, "from_type": "faction", "standing": -2.1},  # Caldari
            {"from_id": 1000125, "from_type": "npc_corp", "standing": 3.2},  # Sisters of EVE
        ]

    return standings


def make_wallet_response(balance: float = 100000000.0) -> float:
    """Create a mock wallet balance response."""
    return balance


def make_location_response(
    solar_system_id: int = 30000142,
    station_id: int | None = 60003760,
    structure_id: int | None = None,
) -> dict[str, Any]:
    """
    Create a mock location response.

    Args:
        solar_system_id: Current solar system ID (default: Jita)
        station_id: Current station ID if docked
        structure_id: Current structure ID if docked at player structure

    Returns:
        Mock location API response
    """
    response = {"solar_system_id": solar_system_id}
    if station_id:
        response["station_id"] = station_id
    if structure_id:
        response["structure_id"] = structure_id
    return response
