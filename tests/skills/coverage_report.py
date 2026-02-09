#!/usr/bin/env python3
"""
Skill Test Coverage Report Generator.

Generates a coverage report showing which skills have:
- JSON Schema definitions
- Test fixtures
- Semantic evaluations (G-Eval configs)
- Ground truth data

Usage:
    uv run python tests/skills/coverage_report.py
    uv run python tests/skills/coverage_report.py --format markdown
    uv run python tests/skills/coverage_report.py --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SkillCoverage:
    """Coverage metrics for a single skill."""

    name: str
    category: str
    has_schema: bool
    fixture_count: int
    has_semantic_eval: bool
    has_ground_truth: bool

    @property
    def coverage_score(self) -> float:
        """
        Calculate coverage score (0.0 - 1.0).

        Formula:
        - 0.3: Has schema
        - 0.3: Has >= 3 fixtures (scaled: 0.1 per fixture up to 3)
        - 0.2: Has semantic eval
        - 0.2: Has ground truth
        """
        score = 0.0
        if self.has_schema:
            score += 0.3
        score += min(self.fixture_count / 3, 1.0) * 0.3
        if self.has_semantic_eval:
            score += 0.2
        if self.has_ground_truth:
            score += 0.2
        return round(score, 2)

    @property
    def coverage_level(self) -> str:
        """Return coverage level classification."""
        score = self.coverage_score
        if score >= 0.8:
            return "high"
        elif score >= 0.5:
            return "medium"
        elif score > 0:
            return "low"
        return "none"


def load_skill_index() -> dict:
    """Load the skill index file."""
    index_path = Path(".claude/skills/_index.json")
    if not index_path.exists():
        print(f"Error: Skill index not found at {index_path}", file=sys.stderr)
        sys.exit(1)

    with open(index_path) as f:
        return json.load(f)


def get_skill_coverage(skill_name: str, category: str) -> SkillCoverage:
    """Calculate coverage for a single skill."""
    base = Path("tests/skills")

    # Check for schema
    schema_path = base / "schemas" / f"{skill_name}.schema.yaml"
    has_schema = schema_path.exists()

    # Count fixtures
    fixtures_dir = base / "fixtures" / skill_name
    fixture_count = len(list(fixtures_dir.glob("*.yaml"))) if fixtures_dir.exists() else 0

    # Check for semantic eval
    eval_path = base / "evals" / f"{skill_name}.eval.yaml"
    has_semantic_eval = eval_path.exists()

    # Check for ground truth (in skill-named subdirectory)
    # Ground truth directories follow pattern: ground_truth/{skill}s/ or ground_truth/{skill}/
    # e.g., ground_truth/routes/ for the /route skill
    ground_truth_dir = base / "ground_truth"
    has_ground_truth = False
    if ground_truth_dir.exists():
        # Check for plural form (routes, fits, missions) or singular (route, fit)
        possible_dirs = [
            ground_truth_dir / f"{skill_name}s",  # e.g., routes, missions
            ground_truth_dir / skill_name,  # e.g., route, mission
        ]
        for subdir in possible_dirs:
            if subdir.is_dir() and any(subdir.glob("*.json")):
                has_ground_truth = True
                break

    return SkillCoverage(
        name=skill_name,
        category=category,
        has_schema=has_schema,
        fixture_count=fixture_count,
        has_semantic_eval=has_semantic_eval,
        has_ground_truth=has_ground_truth,
    )


def generate_report(skills: list[SkillCoverage]) -> dict:
    """Generate coverage report summary."""
    total = len(skills)
    with_schema = sum(1 for s in skills if s.has_schema)
    with_fixtures = sum(1 for s in skills if s.fixture_count > 0)
    with_evals = sum(1 for s in skills if s.has_semantic_eval)
    with_ground_truth = sum(1 for s in skills if s.has_ground_truth)

    coverage_high = sum(1 for s in skills if s.coverage_level == "high")
    coverage_medium = sum(1 for s in skills if s.coverage_level == "medium")
    coverage_low = sum(1 for s in skills if s.coverage_level == "low")
    coverage_none = sum(1 for s in skills if s.coverage_level == "none")

    avg_score = sum(s.coverage_score for s in skills) / total if total > 0 else 0

    return {
        "summary": {
            "total_skills": total,
            "with_schema": with_schema,
            "with_fixtures": with_fixtures,
            "with_semantic_eval": with_evals,
            "with_ground_truth": with_ground_truth,
            "average_coverage_score": round(avg_score, 2),
            "coverage_distribution": {
                "high": coverage_high,
                "medium": coverage_medium,
                "low": coverage_low,
                "none": coverage_none,
            },
        },
        "skills": [
            {
                "name": s.name,
                "category": s.category,
                "has_schema": s.has_schema,
                "fixture_count": s.fixture_count,
                "has_semantic_eval": s.has_semantic_eval,
                "has_ground_truth": s.has_ground_truth,
                "coverage_score": s.coverage_score,
                "coverage_level": s.coverage_level,
            }
            for s in sorted(skills, key=lambda x: (-x.coverage_score, x.name))
        ],
    }


def format_markdown(report: dict) -> str:
    """Format report as markdown."""
    lines = [
        "# Skill Test Coverage Report",
        "",
        "## Summary",
        "",
        f"- **Total Skills:** {report['summary']['total_skills']}",
        f"- **With Schema:** {report['summary']['with_schema']}",
        f"- **With Fixtures:** {report['summary']['with_fixtures']}",
        f"- **With Semantic Eval:** {report['summary']['with_semantic_eval']}",
        f"- **With Ground Truth:** {report['summary']['with_ground_truth']}",
        f"- **Average Coverage Score:** {report['summary']['average_coverage_score']}",
        "",
        "### Coverage Distribution",
        "",
        f"- High (>= 0.8): {report['summary']['coverage_distribution']['high']}",
        f"- Medium (0.5-0.8): {report['summary']['coverage_distribution']['medium']}",
        f"- Low (0.0-0.5): {report['summary']['coverage_distribution']['low']}",
        f"- None (0.0): {report['summary']['coverage_distribution']['none']}",
        "",
        "## Skills by Coverage",
        "",
        "| Skill | Category | Schema | Fixtures | Eval | Truth | Score | Level |",
        "|-------|----------|--------|----------|------|-------|-------|-------|",
    ]

    for skill in report["skills"]:
        check = "✓"
        cross = "✗"
        lines.append(
            f"| {skill['name']} "
            f"| {skill['category']} "
            f"| {check if skill['has_schema'] else cross} "
            f"| {skill['fixture_count']} "
            f"| {check if skill['has_semantic_eval'] else cross} "
            f"| {check if skill['has_ground_truth'] else cross} "
            f"| {skill['coverage_score']} "
            f"| {skill['coverage_level']} |"
        )

    lines.extend(
        [
            "",
            "## Coverage Score Formula",
            "",
            "```",
            "score = (",
            "    0.30 * has_schema +",
            "    0.30 * min(fixture_count / 3, 1.0) +",
            "    0.20 * has_semantic_eval +",
            "    0.20 * has_ground_truth",
            ")",
            "```",
            "",
            "## Next Steps",
            "",
            "Priority for adding coverage (skills with coverage_level='none'):",
            "",
        ]
    )

    none_skills = [s for s in report["skills"] if s["coverage_level"] == "none"]
    for skill in none_skills[:10]:  # Show top 10
        lines.append(f"1. `/{skill['name']}` ({skill['category']})")

    return "\n".join(lines)


def format_console(report: dict) -> str:
    """Format report for console output."""
    lines = [
        "=" * 60,
        "SKILL TEST COVERAGE REPORT",
        "=" * 60,
        "",
        f"Total Skills:         {report['summary']['total_skills']}",
        f"With Schema:          {report['summary']['with_schema']}",
        f"With Fixtures:        {report['summary']['with_fixtures']}",
        f"With Semantic Eval:   {report['summary']['with_semantic_eval']}",
        f"With Ground Truth:    {report['summary']['with_ground_truth']}",
        f"Average Score:        {report['summary']['average_coverage_score']}",
        "",
        "Coverage Distribution:",
        f"  High (>= 0.8):      {report['summary']['coverage_distribution']['high']}",
        f"  Medium (0.5-0.8):   {report['summary']['coverage_distribution']['medium']}",
        f"  Low (0.0-0.5):      {report['summary']['coverage_distribution']['low']}",
        f"  None (0.0):         {report['summary']['coverage_distribution']['none']}",
        "",
        "-" * 60,
        f"{'Skill':<25} {'Cat':<12} {'Sch':<4} {'Fix':<4} {'Evl':<4} {'Tru':<4} {'Score':<6}",
        "-" * 60,
    ]

    for skill in report["skills"]:
        lines.append(
            f"{skill['name']:<25} "
            f"{skill['category'][:10]:<12} "
            f"{'✓' if skill['has_schema'] else '✗':<4} "
            f"{skill['fixture_count']:<4} "
            f"{'✓' if skill['has_semantic_eval'] else '✗':<4} "
            f"{'✓' if skill['has_ground_truth'] else '✗':<4} "
            f"{skill['coverage_score']:<6}"
        )

    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate skill test coverage report")
    parser.add_argument(
        "--format",
        choices=["console", "markdown", "json"],
        default="console",
        help="Output format",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file (default: stdout)",
    )
    args = parser.parse_args()

    # Load skill index
    index = load_skill_index()

    # Calculate coverage for each skill
    skills = []
    for skill in index["skills"]:
        coverage = get_skill_coverage(skill["name"], skill.get("category", "unknown"))
        skills.append(coverage)

    # Generate report
    report = generate_report(skills)

    # Format output
    if args.format == "json":
        output = json.dumps(report, indent=2)
    elif args.format == "markdown":
        output = format_markdown(report)
    else:
        output = format_console(report)

    # Write output
    if args.output:
        args.output.write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
