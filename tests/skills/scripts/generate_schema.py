#!/usr/bin/env python3
"""
Schema Generator for Skill Tests.

Generates JSON Schema YAML files for skill output validation. Schemas are inferred
from skill documentation (SKILL.md) and existing fixtures.

Usage:
    # Generate schema from skill definition
    uv run python tests/skills/scripts/generate_schema.py --skill watchlist

    # Generate with explicit output type hints
    uv run python tests/skills/scripts/generate_schema.py --skill killmail \
        --output-type "killmail_analysis"

    # Dry run (print to stdout)
    uv run python tests/skills/scripts/generate_schema.py --skill assets --dry-run

    # Generate from existing fixture (uses expected_output or mock_responses)
    uv run python tests/skills/scripts/generate_schema.py --skill route \
        --from-fixture tests/skills/fixtures/route/jita_amarr_safe.yaml
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# Common field patterns and their schema types
FIELD_TYPE_PATTERNS = {
    # ID fields
    r".*_id$": {"type": "integer", "minimum": 1},
    r"^id$": {"type": "integer", "minimum": 1},
    r"type_id": {"type": "integer", "minimum": 1, "maximum": 100000000},
    r"system_id": {"type": "integer", "minimum": 30000000, "maximum": 32000000},
    r"region_id": {"type": "integer", "minimum": 10000000, "maximum": 12000000},
    r"character_id": {"type": "integer", "minimum": 90000000},
    r"corporation_id": {"type": "integer", "minimum": 98000000},
    r"alliance_id": {"type": "integer", "minimum": 99000000},

    # Name fields
    r".*_name$": {"type": "string", "minLength": 1},
    r"^name$": {"type": "string", "minLength": 1},
    r"system$": {"type": "string", "minLength": 1},
    r"region$": {"type": "string", "minLength": 1},

    # Security
    r"security$": {"type": "number", "minimum": -1.0, "maximum": 1.0},
    r"security_status": {"type": "number", "minimum": -10.0, "maximum": 10.0},
    r"security_class": {"type": "string", "enum": ["HIGH", "LOW", "NULL"]},

    # Counts and quantities
    r".*_count$": {"type": "integer", "minimum": 0},
    r".*_kills$": {"type": "integer", "minimum": 0},
    r"quantity": {"type": "integer", "minimum": 0},
    r"total_jumps": {"type": "integer", "minimum": 0},
    r"jumps$": {"type": "integer", "minimum": 0},

    # Prices and ISK
    r".*_price$": {"type": ["number", "null"], "minimum": 0},
    r".*_cost$": {"type": "number", "minimum": 0},
    r".*_value$": {"type": "number", "minimum": 0},
    r"isk$": {"type": "number"},
    r"spread": {"type": ["number", "null"]},

    # Percentages
    r".*_percent$": {"type": ["number", "null"]},
    r".*_pct$": {"type": "number"},

    # Timestamps
    r".*_at$": {"type": "string", "format": "date-time"},
    r"timestamp": {"type": "string"},
    r".*_date$": {"type": "string"},

    # Boolean flags
    r"^is_.*": {"type": "boolean"},
    r"^has_.*": {"type": "boolean"},
    r"^can_.*": {"type": "boolean"},

    # Enums based on field name
    r"mode$": {"type": "string", "enum": ["shortest", "safe", "unsafe"]},
    r"freshness$": {"type": "string", "enum": ["fresh", "stale", "cached"]},
    r"source$": {"type": "string", "enum": ["fuzzwork", "esi", "esi_orders", "cache"]},
    r"activity_level": {"type": "string", "enum": ["quiet", "low", "moderate", "high", "extreme"]},
    r"risk_level": {"type": "string", "enum": ["minimal", "low", "moderate", "high", "extreme"]},
    r"tier$": {"type": "string", "enum": ["P0", "P1", "P2", "P3", "P4"]},
}


def infer_type_from_name(field_name: str) -> dict[str, Any] | None:
    """
    Infer JSON Schema type from field name patterns.

    Args:
        field_name: The field name to analyze

    Returns:
        Schema fragment or None if no pattern matches
    """
    for pattern, schema in FIELD_TYPE_PATTERNS.items():
        if re.match(pattern, field_name, re.IGNORECASE):
            return schema.copy()
    return None


def infer_type_from_value(value: Any) -> dict[str, Any]:
    """
    Infer JSON Schema type from a sample value.

    Args:
        value: Sample value to analyze

    Returns:
        Schema fragment
    """
    if value is None:
        return {"type": "null"}
    elif isinstance(value, bool):
        return {"type": "boolean"}
    elif isinstance(value, int):
        return {"type": "integer"}
    elif isinstance(value, float):
        return {"type": "number"}
    elif isinstance(value, str):
        return {"type": "string"}
    elif isinstance(value, list):
        if len(value) > 0:
            # Infer item type from first element
            item_schema = infer_type_from_value(value[0])
            return {"type": "array", "items": item_schema}
        return {"type": "array"}
    elif isinstance(value, dict):
        return {"type": "object"}
    else:
        return {}


def generate_schema_from_sample(
    sample: dict[str, Any],
    title: str | None = None,
    description: str | None = None,
    required_fields: list[str] | None = None,
) -> dict[str, Any]:
    """
    Generate a JSON Schema from a sample response object.

    Args:
        sample: Sample response dictionary
        title: Schema title
        description: Schema description
        required_fields: List of required field names (auto-inferred if None)

    Returns:
        JSON Schema dictionary
    """
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
    }

    if title:
        schema["title"] = title
    if description:
        schema["description"] = description

    schema["type"] = "object"

    # Generate properties
    properties = {}
    definitions = {}

    for key, value in sample.items():
        prop_schema = generate_property_schema(key, value, definitions)
        properties[key] = prop_schema

    schema["properties"] = properties

    # Determine required fields
    if required_fields is None:
        # Auto-infer: common required patterns
        required_fields = []
        required_patterns = [
            "origin", "destination", "total_jumps", "mode", "route",
            "items", "region", "region_id", "source", "freshness",
            "type_id", "type_name", "name", "system", "security",
        ]
        for key in sample.keys():
            if key in required_patterns:
                required_fields.append(key)

    if required_fields:
        schema["required"] = required_fields

    # Add definitions if any
    if definitions:
        schema["$defs"] = definitions

    return schema


def generate_property_schema(
    key: str,
    value: Any,
    definitions: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate schema for a single property.

    Args:
        key: Property name
        value: Sample value
        definitions: Dictionary to collect $defs

    Returns:
        Property schema
    """
    # First try name-based inference
    name_schema = infer_type_from_name(key)
    if name_schema:
        return name_schema

    # Fall back to value-based inference
    schema = infer_type_from_value(value)

    # Handle complex nested objects
    if isinstance(value, dict) and value:
        # Check if this is a reusable type
        if key in ["buy", "sell"]:
            def_name = "OrderStats"
            if def_name not in definitions:
                definitions[def_name] = generate_schema_from_sample(
                    value,
                    title=def_name,
                    description="Market order statistics",
                )
            return {"$ref": f"#/$defs/{def_name}"}

        if key == "security_profile":
            def_name = "SecurityProfile"
            if def_name not in definitions:
                definitions[def_name] = {
                    "type": "object",
                    "properties": {
                        "highsec_jumps": {"type": "integer", "minimum": 0},
                        "lowsec_jumps": {"type": "integer", "minimum": 0},
                        "nullsec_jumps": {"type": "integer", "minimum": 0},
                    },
                }
            return {"$ref": f"#/$defs/{def_name}"}

        # Generate inline object schema
        schema["properties"] = {}
        for sub_key, sub_value in value.items():
            schema["properties"][sub_key] = generate_property_schema(
                sub_key, sub_value, definitions
            )

    # Handle arrays with complex items
    if isinstance(value, list) and len(value) > 0:
        first = value[0]
        if isinstance(first, dict):
            # Check for known item types
            if key == "route":
                def_name = "RouteSystem"
                if def_name not in definitions:
                    definitions[def_name] = {
                        "type": "object",
                        "required": ["system", "security"],
                        "properties": {
                            "system": {"type": "string", "minLength": 1},
                            "system_id": {"type": "integer", "minimum": 30000000},
                            "security": {"type": "number", "minimum": -1.0, "maximum": 1.0},
                            "is_border": {"type": "boolean"},
                            "region": {"type": "string"},
                        },
                    }
                schema["items"] = {"$ref": f"#/$defs/{def_name}"}

            elif key == "items" and "type_id" in first:
                def_name = "PriceItem"
                if def_name not in definitions:
                    item_schema = generate_schema_from_sample(first)
                    item_schema["title"] = def_name
                    definitions[def_name] = item_schema
                schema["items"] = {"$ref": f"#/$defs/{def_name}"}

            elif key == "systems" and "security" in first:
                def_name = "SystemInfo"
                if def_name not in definitions:
                    definitions[def_name] = generate_schema_from_sample(
                        first,
                        title=def_name,
                    )
                schema["items"] = {"$ref": f"#/$defs/{def_name}"}

            else:
                # Generate inline item schema
                schema["items"] = generate_schema_from_sample(first)

    return schema


def load_skill_definition(skill_name: str) -> dict[str, Any] | None:
    """
    Load skill definition from SKILL.md and extract output format hints.

    Args:
        skill_name: Name of the skill

    Returns:
        Parsed hints or None
    """
    skill_path = Path(f".claude/skills/{skill_name}/SKILL.md")
    if not skill_path.exists():
        return None

    content = skill_path.read_text()

    # Try to extract output format section
    hints = {}

    # Look for "## Output" or "## Response Format" sections
    output_match = re.search(
        r"##\s*(Output|Response Format|Output Format)\s*\n(.*?)(?=\n##|\Z)",
        content,
        re.IGNORECASE | re.DOTALL,
    )

    if output_match:
        hints["output_section"] = output_match.group(2).strip()

    # Look for JSON/YAML code blocks that might show output structure
    code_blocks = re.findall(r"```(?:json|yaml)?\s*\n(.*?)\n```", content, re.DOTALL)
    hints["code_blocks"] = code_blocks

    return hints


def schema_to_yaml(schema: dict[str, Any]) -> str:
    """
    Convert schema dict to well-formatted YAML.

    Args:
        schema: JSON Schema dictionary

    Returns:
        YAML string
    """
    # Custom representer for better formatting
    def str_representer(dumper, data):
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    yaml.add_representer(str, str_representer)

    return yaml.dump(
        schema,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )


def generate_schema_from_fixture(fixture_path: Path) -> dict[str, Any]:
    """
    Generate schema from an existing fixture file.

    Args:
        fixture_path: Path to fixture YAML

    Returns:
        Generated schema
    """
    with open(fixture_path) as f:
        fixture = yaml.safe_load(f)

    skill_name = fixture.get("skill", fixture_path.parent.name)

    # Try expected_output first, then mock_responses
    sample = None
    if "expected_output" in fixture:
        sample = fixture["expected_output"]
    elif "mock_responses" in fixture:
        # Use the first mock response as sample
        for _key, response in fixture["mock_responses"].items():
            sample = response
            break

    if sample is None:
        raise ValueError(f"No sample data found in fixture: {fixture_path}")

    return generate_schema_from_sample(
        sample,
        title=f"{skill_name.replace('-', ' ').title()}SkillOutput",
        description=f"Output schema for the /{skill_name} skill",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate JSON Schema for ARIA skill outputs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--skill",
        required=True,
        help="Skill name (e.g., watchlist, killmail, assets)",
    )
    parser.add_argument(
        "--from-fixture",
        type=Path,
        help="Generate schema from existing fixture file",
    )
    parser.add_argument(
        "--output-type",
        help="Output type hint for schema title",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/skills/schemas"),
        help="Output directory (default: tests/skills/schemas)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print YAML to stdout instead of writing file",
    )
    args = parser.parse_args()

    # Generate schema
    if args.from_fixture:
        if not args.from_fixture.exists():
            print(f"Error: Fixture not found: {args.from_fixture}", file=sys.stderr)
            sys.exit(1)
        schema = generate_schema_from_fixture(args.from_fixture)
    else:
        # Try to load from skill definition (validates skill exists)
        load_skill_definition(args.skill)

        # Check for existing fixtures
        fixtures_dir = Path(f"tests/skills/fixtures/{args.skill}")
        if fixtures_dir.exists():
            fixtures = list(fixtures_dir.glob("*.yaml"))
            if fixtures:
                print(f"Generating schema from fixture: {fixtures[0]}", file=sys.stderr)
                schema = generate_schema_from_fixture(fixtures[0])
            else:
                print(f"Error: No fixtures found for skill '{args.skill}'", file=sys.stderr)
                print("Use --from-fixture or create fixtures first.", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Error: No fixtures found for skill '{args.skill}'", file=sys.stderr)
            print("Use --from-fixture or create fixtures first.", file=sys.stderr)
            sys.exit(1)

    # Override title if specified
    if args.output_type:
        schema["title"] = f"{args.output_type}Output"

    # Add header comment
    yaml_content = f"""# JSON Schema for /{args.skill} skill output validation
# Generated by generate_schema.py
# Review and adjust constraints as needed

{schema_to_yaml(schema)}"""

    if args.dry_run:
        print(yaml_content)
        return

    # Write schema file
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"{args.skill}.schema.yaml"

    output_path.write_text(yaml_content)
    print(f"Generated: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
