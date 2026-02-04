"""
Skill invocation strategies for different test tiers.

Provides three invocation methods:
- Tier 1: Direct MCP dispatcher calls with mocked responses
- Tier 2: Anthropic API calls with mock tool responses
- Tier 3: Full Claude CLI invocation
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from typing import Any

from tests.skills.integration.mcp_mocker import MockMCPServer

# =============================================================================
# Tier 1: Direct MCP Dispatcher Invocation
# =============================================================================


def invoke_mcp_direct(
    dispatcher: str,
    action: str,
    mock_server: MockMCPServer | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Tier 1: Invoke MCP dispatcher directly with optional mocking.

    This is the fastest invocation method - no API calls, no subprocess.
    Used for validating MCP contracts and response structure.

    Args:
        dispatcher: The MCP dispatcher name (sde, market, universe, etc.)
        action: The action parameter value
        mock_server: Optional MockMCPServer for returning fixture data
        **kwargs: Additional parameters for the dispatcher

    Returns:
        Dispatcher response (mocked or real)

    Example:
        result = invoke_mcp_direct(
            "sde", "blueprint_info",
            mock_server=server,
            item="Venture"
        )
    """
    if mock_server is not None:
        # Return mock response
        return mock_server.mock_call(dispatcher, action, **kwargs)

    # Try to import and call the actual dispatcher
    try:
        if dispatcher == "sde":
            from aria_esi.mcp.dispatchers.sde import sde

            return asyncio.get_event_loop().run_until_complete(sde(action=action, **kwargs))
        elif dispatcher == "market":
            from aria_esi.mcp.dispatchers.market import market

            return asyncio.get_event_loop().run_until_complete(market(action=action, **kwargs))
        elif dispatcher == "universe":
            from aria_esi.mcp.dispatchers.universe import universe

            return asyncio.get_event_loop().run_until_complete(universe(action=action, **kwargs))
        elif dispatcher == "skills":
            from aria_esi.mcp.dispatchers.skills import skills

            return asyncio.get_event_loop().run_until_complete(skills(action=action, **kwargs))
        elif dispatcher == "fitting":
            from aria_esi.mcp.dispatchers.fitting import fitting

            return asyncio.get_event_loop().run_until_complete(fitting(action=action, **kwargs))
        elif dispatcher == "status":
            from aria_esi.mcp.dispatchers.status import status

            return asyncio.get_event_loop().run_until_complete(status())
        else:
            raise ValueError(f"Unknown dispatcher: {dispatcher}")

    except ImportError as e:
        raise ImportError(f"Cannot import dispatcher '{dispatcher}': {e}") from e


# =============================================================================
# Tier 2: Anthropic API Invocation
# =============================================================================


async def invoke_via_api(
    skill_name: str,
    skill_args: str,
    mock_tools: dict[str, Any] | None = None,
    model: str = "claude-3-5-haiku-20241022",
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """
    Tier 2: Invoke skill via Anthropic API with mock tool responses.

    This method calls the Anthropic API but intercepts tool use requests
    to return mock responses instead of calling real MCP servers.

    Cost: ~$0.01 per test

    Args:
        skill_name: Name of the skill to invoke (e.g., "build-cost")
        skill_args: Arguments to pass to the skill
        mock_tools: Dict mapping tool_name to mock responses
        model: Model to use (default: Haiku for cost efficiency)
        max_tokens: Maximum tokens in response

    Returns:
        Dict with:
        - response: The final text response
        - tool_calls: List of tool calls made
        - tool_results: List of tool results returned

    Raises:
        ImportError: If anthropic is not installed
        ValueError: If ANTHROPIC_API_KEY is not set
    """
    try:
        import anthropic
    except ImportError as e:
        raise ImportError("anthropic package required for Tier 2 tests") from e

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable required for Tier 2 tests")

    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Define the tool schemas that match MCP dispatchers
    tools = [
        {
            "name": "sde",
            "description": "Query EVE Online Static Data Export",
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "item": {"type": "string"},
                },
                "required": ["action"],
            },
        },
        {
            "name": "market",
            "description": "Query EVE Online market data",
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "string"}},
                    "region": {"type": "string"},
                },
                "required": ["action"],
            },
        },
        {
            "name": "universe",
            "description": "Query EVE Online universe data",
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "mode": {"type": "string"},
                },
                "required": ["action"],
            },
        },
    ]

    # Build the prompt
    prompt = f"Execute the /{skill_name} skill with arguments: {skill_args}\n\nReturn the result as JSON."

    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    tool_calls = []
    tool_results = []

    # Agentic loop - handle tool use
    while True:
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            tools=tools,
            messages=messages,
        )

        # Check if we need to handle tool use
        if response.stop_reason == "tool_use":
            # Process each tool use block
            assistant_content = []
            tool_use_results = []

            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tool_use_id = block.id

                    tool_calls.append({"name": tool_name, "input": tool_input})

                    # Get mock response if available
                    if mock_tools and tool_name in mock_tools:
                        action = tool_input.get("action", "")
                        mock_key = f"{tool_name}_{action}"
                        mock_response = mock_tools.get(mock_key, mock_tools.get(tool_name, {}))
                    else:
                        mock_response = {"error": f"No mock configured for {tool_name}"}

                    tool_results.append({"tool": tool_name, "result": mock_response})

                    tool_use_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": json.dumps(mock_response),
                        }
                    )

                assistant_content.append(block)

            # Add assistant message with tool use
            messages.append({"role": "assistant", "content": assistant_content})
            # Add tool results
            messages.append({"role": "user", "content": tool_use_results})

        else:
            # Final response - extract text
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            return {
                "response": final_text,
                "tool_calls": tool_calls,
                "tool_results": tool_results,
            }


# =============================================================================
# Tier 3: Full Claude CLI Invocation
# =============================================================================


def invoke_via_cli(
    skill_name: str,
    skill_args: str = "",
    timeout: int = 60,
    cwd: str | None = None,
) -> dict[str, Any]:
    """
    Tier 3: Invoke skill via full Claude CLI.

    This is the most complete test but slowest and most expensive.
    Uses the actual Claude CLI with --print flag for non-interactive output.

    Cost: ~$0.03 per test

    Args:
        skill_name: Name of the skill to invoke
        skill_args: Arguments to pass to the skill
        timeout: Command timeout in seconds
        cwd: Working directory for the command

    Returns:
        Dict with:
        - response: The raw CLI output
        - return_code: Process return code
        - success: Boolean indicating success

    Raises:
        TimeoutError: If the command times out
    """
    # Build the command
    prompt = f"/{skill_name}"
    if skill_args:
        prompt += f" {skill_args}"

    cmd = ["claude", "--print", "-p", prompt]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or os.getcwd(),
            env={**os.environ, "NO_COLOR": "1"},  # Disable color codes
        )

        return {
            "response": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "success": result.returncode == 0,
        }

    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"CLI command timed out after {timeout}s") from e
    except FileNotFoundError as e:
        raise FileNotFoundError("'claude' CLI not found. Is Claude Code installed?") from e


# =============================================================================
# Helper: Run async in sync context
# =============================================================================


def run_async(coro: Any) -> Any:
    """
    Run an async coroutine in a synchronous context.

    Handles the case where an event loop may already be running.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        return asyncio.run(coro)
    else:
        # Already in an async context, use nest_asyncio or similar
        import nest_asyncio

        nest_asyncio.apply()
        return asyncio.run(coro)
