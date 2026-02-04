"""
Integration test infrastructure for skill testing.

This module provides utilities for invoking skills at different tiers:
- Tier 1: Mock MCP dispatcher directly (fast, no cost)
- Tier 2: Anthropic API with mock tools (weekly CI)
- Tier 3: Full Claude CLI (release/manual)

Exports:
    MockMCPServer: Mock MCP server that returns fixture data
    MockESIServer: Mock ESI server for API call simulation
    inject_mock_responses: Patches dispatchers with fixture responses
    inject_esi_mocks: Patches ESI client with fixture responses
    invoke_mcp_direct: Direct MCP dispatcher invocation
    invoke_via_api: Anthropic API invocation with mock tools
    invoke_via_cli: Full Claude CLI invocation
    extract_json_from_response: Enhanced JSON extraction from LLM responses
    extract_facts_from_prose: Extract facts from prose responses
"""

from __future__ import annotations

from tests.skills.integration.esi_mocker import (
    MockESIServer,
    inject_esi_mocks,
    load_fixture_with_esi_mocks,
    make_assets_response,
    make_location_response,
    make_skillqueue_response,
    make_skills_response,
    make_standings_response,
    make_wallet_response,
)
from tests.skills.integration.invokers import (
    invoke_mcp_direct,
    invoke_via_api,
    invoke_via_cli,
)
from tests.skills.integration.mcp_mocker import (
    MockMCPServer,
    inject_mock_responses,
    load_fixture_with_mocks,
)
from tests.skills.integration.response_parser import (
    extract_facts_from_prose,
    extract_json_from_response,
)

__all__ = [
    # MCP mocking
    "MockMCPServer",
    "inject_mock_responses",
    "load_fixture_with_mocks",
    # ESI mocking
    "MockESIServer",
    "inject_esi_mocks",
    "load_fixture_with_esi_mocks",
    "make_skills_response",
    "make_skillqueue_response",
    "make_assets_response",
    "make_standings_response",
    "make_wallet_response",
    "make_location_response",
    # Invokers
    "invoke_mcp_direct",
    "invoke_via_api",
    "invoke_via_cli",
    # Response parsing
    "extract_json_from_response",
    "extract_facts_from_prose",
]
