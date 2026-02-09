#!/usr/bin/env python3
"""
Fixture Generator for Skill Tests.

Generates test fixture YAML files by invoking MCP dispatchers and capturing
their responses. Fixtures include both mock_responses and expected_facts
for use in Tier 1 (contract) and Tier 2 (structural) validation.

Usage:
    # Generate a route fixture
    uv run python tests/skills/scripts/generate_fixture.py --skill route \
        --input '{"origin": "Jita", "destination": "Amarr", "mode": "safe"}' \
        --name "jita_amarr_safe"

    # Generate a price fixture
    uv run python tests/skills/scripts/generate_fixture.py --skill price \
        --input '{"items": ["Tritanium", "Pyerite"], "region": "jita"}' \
        --name "minerals_jita"

    # Generate with description
    uv run python tests/skills/scripts/generate_fixture.py --skill build-cost \
        --input '{"item": "Venture", "me": 0}' \
        --name "venture_me0" \
        --description "Basic Venture build cost at ME 0"

    # Dry run (print to stdout)
    uv run python tests/skills/scripts/generate_fixture.py --skill route \
        --input '{"origin": "Jita", "destination": "Perimeter"}' \
        --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Dispatcher to action mapping for common skills
SKILL_DISPATCHER_MAPPING = {
    "route": [("universe", "route")],
    "price": [("market", "prices")],
    "find": [("market", "find_nearby")],
    "build-cost": [("sde", "blueprint_info"), ("market", "prices")],
    "arbitrage": [("market", "arbitrage_scan")],
    "skillplan": [("sde", "skill_requirements"), ("skills", "easy_80_plan")],
    "orient": [("universe", "local_area")],
    "gatecamp": [("universe", "gatecamp_risk")],
    "threat-assessment": [("universe", "activity")],
    "fitting": [("fitting", "calculate_stats")],
    "abyssal": [],  # Reference data only
    "pi": [],  # Reference data only
    "standings": [],  # ESI-dependent
    "watchlist": [],  # Local data + optional ESI
    "killmail": [],  # External zkillboard
    "assets": [],  # ESI-dependent
}


def get_dispatcher_key(dispatcher: str, action: str) -> str:
    """Create fixture key from dispatcher and action."""
    return f"{dispatcher}_{action}"


async def invoke_dispatcher(
    dispatcher: str,
    action: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Invoke an MCP dispatcher and return its response.

    Args:
        dispatcher: MCP dispatcher name (sde, market, universe, etc.)
        action: Action parameter
        **kwargs: Additional parameters for the dispatcher

    Returns:
        Dispatcher response dictionary
    """
    try:
        if dispatcher == "sde":
            from aria_esi.mcp.dispatchers.sde import sde

            return await sde(action=action, **kwargs)
        elif dispatcher == "market":
            from aria_esi.mcp.dispatchers.market import market

            return await market(action=action, **kwargs)
        elif dispatcher == "universe":
            from aria_esi.mcp.dispatchers.universe import universe

            return await universe(action=action, **kwargs)
        elif dispatcher == "skills":
            from aria_esi.mcp.dispatchers.skills import skills

            return await skills(action=action, **kwargs)
        elif dispatcher == "fitting":
            from aria_esi.mcp.dispatchers.fitting import fitting

            return await fitting(action=action, **kwargs)
        elif dispatcher == "status":
            from aria_esi.mcp.dispatchers.status import status

            return await status()
        else:
            raise ValueError(f"Unknown dispatcher: {dispatcher}")

    except ImportError as e:
        print(f"Warning: Cannot import dispatcher '{dispatcher}': {e}", file=sys.stderr)
        return {"error": f"Dispatcher not available: {dispatcher}"}
    except Exception as e:
        print(f"Warning: Error invoking {dispatcher}.{action}: {e}", file=sys.stderr)
        return {"error": str(e)}


def infer_expected_facts(
    response: dict[str, Any],
    input_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Infer expected_facts from a response based on common patterns.

    Args:
        response: The dispatcher response
        input_data: The input parameters

    Returns:
        List of fact assertions
    """
    facts = []

    # Direct field matching from input
    for key in ["origin", "destination", "mode", "region"]:
        if key in response and key in input_data:
            facts.append({"path": key, "equals": response[key]})

    # Route-specific facts
    if "route" in response and isinstance(response["route"], list):
        if len(response["route"]) > 0:
            first_system = response["route"][0]
            if "system" in first_system:
                facts.append({"path": "route[0].system", "equals": first_system["system"]})

            last_system = response["route"][-1]
            if "system" in last_system:
                facts.append({"path": "route[-1].system", "equals": last_system["system"]})

        if "total_jumps" in response:
            # Allow some variance for route changes
            total = response["total_jumps"]
            facts.append({"path": "total_jumps", "range": [max(0, total - 5), total + 5]})

    # Security profile facts
    if "security_profile" in response:
        profile = response["security_profile"]
        for key in ["highsec_jumps", "lowsec_jumps", "nullsec_jumps"]:
            if key in profile and profile[key] == 0:
                facts.append({"path": f"security_profile.{key}", "equals": 0})

    # Price-specific facts
    if "items" in response and isinstance(response["items"], list):
        if len(response["items"]) > 0:
            facts.append(
                {"path": "items[*].type_id", "all_satisfy": ">= 1"}
            )

    # Market/region facts
    if "region_id" in response:
        facts.append(
            {"path": "region_id", "range": [10000000, 12000000]}
        )

    return facts


def generate_fixture_yaml(
    skill_name: str,
    input_data: dict[str, Any],
    mock_responses: dict[str, Any],
    expected_facts: list[dict[str, Any]],
    name: str,
    description: str | None = None,
) -> str:
    """
    Generate the fixture YAML content.

    Args:
        skill_name: Name of the skill
        input_data: Input parameters
        mock_responses: MCP responses to mock
        expected_facts: Facts to validate
        name: Fixture name/title
        description: Optional description

    Returns:
        YAML string
    """
    # Build fixture structure
    fixture = {
        "name": name.replace("_", " ").title(),
        "skill": skill_name,
    }

    if description:
        fixture["description"] = description

    fixture["input"] = input_data

    if expected_facts:
        fixture["expected_facts"] = expected_facts

    # Add section separator and mock responses
    lines = [
        f"# Test fixture: {name}",
        f"# Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    # Use custom YAML dumper for better formatting
    yaml_content = yaml.dump(
        fixture,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )
    lines.append(yaml_content)

    if mock_responses:
        lines.extend([
            "# =============================================================================",
            "# Mock MCP Responses for Tier 1 Integration Tests",
            "# =============================================================================",
            "",
        ])

        mock_section = {"mock_responses": mock_responses}
        mock_yaml = yaml.dump(
            mock_section,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=100,
        )
        lines.append(mock_yaml)

    return "\n".join(lines)


async def generate_fixture(
    skill_name: str,
    input_data: dict[str, Any],
    name: str,
    description: str | None = None,
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> str:
    """
    Generate a complete test fixture for a skill.

    Args:
        skill_name: Name of the skill
        input_data: Input parameters as dict
        name: Fixture filename (without extension)
        description: Optional description
        output_dir: Output directory (default: tests/skills/fixtures/{skill})
        dry_run: If True, print to stdout instead of writing file

    Returns:
        Path to generated fixture or YAML content if dry_run
    """
    # Get dispatcher mapping for this skill
    dispatchers = SKILL_DISPATCHER_MAPPING.get(skill_name, [])

    mock_responses = {}
    all_facts = []

    # Invoke each dispatcher and capture response
    for dispatcher, action in dispatchers:
        # Map input parameters to dispatcher parameters
        params = map_input_to_dispatcher_params(dispatcher, action, input_data)

        print(f"Invoking {dispatcher}(action={action!r}, ...)", file=sys.stderr)
        response = await invoke_dispatcher(dispatcher, action, **params)

        if "error" not in response:
            key = get_dispatcher_key(dispatcher, action)
            mock_responses[key] = response

            # Infer facts from response
            facts = infer_expected_facts(response, input_data)
            all_facts.extend(facts)
        else:
            print(f"  Warning: {response['error']}", file=sys.stderr)

    # Generate YAML
    yaml_content = generate_fixture_yaml(
        skill_name=skill_name,
        input_data=input_data,
        mock_responses=mock_responses,
        expected_facts=all_facts,
        name=name,
        description=description,
    )

    if dry_run:
        return yaml_content

    # Determine output path
    if output_dir is None:
        output_dir = Path("tests/skills/fixtures") / skill_name

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}.yaml"

    output_path.write_text(yaml_content)
    print(f"Generated: {output_path}", file=sys.stderr)

    return str(output_path)


def map_input_to_dispatcher_params(
    dispatcher: str,
    action: str,
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Map skill input parameters to dispatcher-specific parameters.

    Args:
        dispatcher: MCP dispatcher name
        action: Dispatcher action
        input_data: Original input parameters

    Returns:
        Parameters suitable for the dispatcher
    """
    params = {}

    if dispatcher == "universe":
        if action == "route":
            params = {
                k: input_data[k]
                for k in ["origin", "destination", "mode", "avoid_systems"]
                if k in input_data
            }
        elif action == "local_area":
            params = {
                k: input_data[k]
                for k in ["origin", "max_jumps", "include_realtime"]
                if k in input_data
            }
        elif action == "activity":
            params = {"systems": input_data.get("systems", [])}
        elif action == "gatecamp_risk":
            if "route" in input_data:
                params = {"route": input_data["route"]}
            else:
                params = {
                    k: input_data[k]
                    for k in ["origin", "destination", "mode"]
                    if k in input_data
                }

    elif dispatcher == "market":
        if action == "prices":
            params = {
                "items": input_data.get("items", []),
                "region": input_data.get("region", "jita"),
            }
        elif action == "find_nearby":
            params = {
                "item": input_data.get("item"),
                "origin": input_data.get("origin", "Jita"),
                "max_jumps": input_data.get("max_jumps", 20),
                "source_filter": input_data.get("source_filter", "all"),
            }
        elif action == "arbitrage_scan":
            params = {
                k: input_data[k]
                for k in ["min_profit_pct", "min_volume", "buy_from", "sell_to", "sort_by"]
                if k in input_data
            }

    elif dispatcher == "sde":
        if action == "blueprint_info":
            params = {"item": input_data.get("item")}
        elif action == "skill_requirements":
            params = {
                "item": input_data.get("item"),
                "include_prerequisites": input_data.get("include_prerequisites", True),
            }

    elif dispatcher == "skills":
        if action == "easy_80_plan":
            params = {"item": input_data.get("item")}
        elif action == "training_time":
            params = {"skill_list": input_data.get("skill_list", [])}

    elif dispatcher == "fitting":
        if action == "calculate_stats":
            params = {
                "eft": input_data.get("eft"),
                "use_pilot_skills": input_data.get("use_pilot_skills", False),
            }

    return params


def main():
    parser = argparse.ArgumentParser(
        description="Generate test fixtures for ARIA skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--skill",
        required=True,
        help="Skill name (e.g., route, price, build-cost)",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input parameters as JSON string",
    )
    parser.add_argument(
        "--name",
        help="Fixture filename (without .yaml extension)",
    )
    parser.add_argument(
        "--description",
        help="Optional description for the fixture",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: tests/skills/fixtures/{skill})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print YAML to stdout instead of writing file",
    )
    args = parser.parse_args()

    # Parse input JSON
    try:
        input_data = json.loads(args.input)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate fixture name if not provided
    name = args.name
    if not name:
        # Try to auto-generate from input
        parts = []
        if "origin" in input_data:
            parts.append(input_data["origin"].lower())
        if "destination" in input_data:
            parts.append(input_data["destination"].lower())
        if "item" in input_data:
            parts.append(input_data["item"].lower().replace(" ", "_"))
        if "mode" in input_data:
            parts.append(input_data["mode"])
        if "items" in input_data and input_data["items"]:
            parts.append(input_data["items"][0].lower())

        name = "_".join(parts) if parts else f"{args.skill}_fixture"

    # Run async generator
    result = asyncio.run(
        generate_fixture(
            skill_name=args.skill,
            input_data=input_data,
            name=name,
            description=args.description,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
        )
    )

    if args.dry_run:
        print(result)


if __name__ == "__main__":
    main()
