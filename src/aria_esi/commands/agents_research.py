"""
ARIA ESI Research Agents Commands

Monitor research agent partnerships and accumulated research points.
All commands require authentication.
"""

import argparse
from datetime import datetime, timezone

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    get_authenticated_client,
    get_utc_timestamp,
    parse_datetime,
)

# =============================================================================
# Research Agents Command
# =============================================================================


def cmd_agents_research(args: argparse.Namespace) -> dict:
    """
    Fetch research agent partnerships and accumulated RP.

    Shows active research agreements, daily RP rates, and calculated
    accumulated points based on time elapsed.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id

    # Check scope
    if not creds.has_scope("esi-characters.read_agents_research.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-characters.read_agents_research.v1",
            "action": "Re-run OAuth setup to authorize research agents access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    public_client = ESIClient()

    # Fetch research agents
    try:
        agents_data = client.get_list(f"/characters/{char_id}/agents_research/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch research agents: {e.message}",
            "hint": "Ensure esi-characters.read_agents_research.v1 scope is authorized",
            "query_timestamp": query_ts,
        }

    # Empty check
    if not agents_data:
        return {
            "query_timestamp": query_ts,
            "volatility": "stable",
            "character_id": char_id,
            "summary": {"total_agents": 0, "total_daily_rp": 0, "total_accumulated_rp": 0},
            "agents": [],
            "message": "No active research agents",
        }

    now = datetime.now(timezone.utc)

    # Collect IDs for resolution
    agent_ids = set()
    skill_type_ids = set()
    for agent in agents_data:
        if isinstance(agent, dict):
            agent_ids.add(agent.get("agent_id", 0))
            skill_type_ids.add(agent.get("skill_type_id", 0))

    # Resolve agent names (agents are NPCs, lookup via /universe/agents/)
    # Note: ESI doesn't have a direct agent name endpoint, but we can try characters
    # For NPC agents, we'll use a fallback
    agent_names = {}
    agent_corps = {}
    for aid in agent_ids:
        if aid:
            # Try to get agent info - NPC agents may not have public endpoints
            # We'll provide agent ID as fallback
            agent_names[aid] = f"Agent-{aid}"
            agent_corps[aid] = "Unknown Corp"

    # Resolve skill type names
    skill_names = {}
    for tid in skill_type_ids:
        if tid:
            info = public_client.get_dict_safe(f"/universe/types/{tid}/")
            if info and "name" in info:
                skill_names[tid] = info["name"]
            else:
                skill_names[tid] = f"Skill-{tid}"

    # Process agents
    processed_agents = []
    total_daily_rp = 0.0
    total_accumulated_rp = 0.0

    for agent in agents_data:
        agent_id = agent.get("agent_id", 0)
        skill_type_id = agent.get("skill_type_id", 0)
        started_at = parse_datetime(agent.get("started_at"))
        points_per_day = agent.get("points_per_day", 0.0)
        remainder_points = agent.get("remainder_points", 0.0)

        # Calculate days active and accumulated RP
        days_active: float = 0.0
        accumulated_rp = remainder_points

        if started_at:
            delta = now - started_at
            days_active = delta.days + (delta.seconds / 86400.0)
            accumulated_rp = remainder_points + (points_per_day * days_active)

        total_daily_rp += points_per_day
        total_accumulated_rp += accumulated_rp

        processed_agent = {
            "agent_id": agent_id,
            "agent_name": agent_names.get(agent_id, f"Agent-{agent_id}"),
            "agent_corp": agent_corps.get(agent_id, "Unknown Corp"),
            "skill_type_id": skill_type_id,
            "skill_name": skill_names.get(skill_type_id, f"Skill-{skill_type_id}"),
            "started_at": agent.get("started_at"),
            "points_per_day": round(points_per_day, 1),
            "remainder_points": round(remainder_points, 1),
            "accumulated_rp": round(accumulated_rp, 0),
            "days_active": round(days_active, 0),
        }

        processed_agents.append(processed_agent)

    # Sort by accumulated RP (highest first)
    processed_agents.sort(key=lambda a: a["accumulated_rp"], reverse=True)

    return {
        "query_timestamp": query_ts,
        "volatility": "stable",
        "character_id": char_id,
        "summary": {
            "total_agents": len(processed_agents),
            "total_daily_rp": round(total_daily_rp, 1),
            "total_accumulated_rp": round(total_accumulated_rp, 0),
        },
        "agents": processed_agents,
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register research agents command parsers."""

    parser = subparsers.add_parser(
        "agents-research", help="Show research agent partnerships and accumulated RP"
    )
    parser.set_defaults(func=cmd_agents_research)
