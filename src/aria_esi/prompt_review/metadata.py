"""Prompt metadata validation for v1 prompt files.

Validates required headers: owner, last_reviewed, depends_on, adjacent_prompts.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Required metadata fields per the proposal's ownership and maintenance SLA
REQUIRED_METADATA_FIELDS = {"owner", "last_reviewed", "depends_on", "adjacent_prompts"}

# Cutover date: before this, missing metadata is a warning; on/after, it's a failure
METADATA_CUTOVER = datetime(2026, 3, 31, 0, 0, 0, tzinfo=UTC)

# v1 prompt registry: canonical paths for all 14 v1 prompts
V1_PROMPT_PATHS = [
    "meta/review_orchestrator.md",
    "meta/scoring_rubric.md",
    "architecture/system_design.md",
    "architecture/mcp_architecture.md",
    "security/audit_ai.md",
    "security/supply_chain_and_dependencies.md",
    "testing/test_harness.md",
    "testing/coverage_quality.md",
    "cicd/pipeline_quality.md",
    "cicd/release_and_rollback.md",
    "docs/onboarding_first_run_ux.md",
    "repo/github_first_impression.md",
    "dev/premerge.md",
    "dev/postmerge_regression_audit.md",
]

# Prompt ID registry: derived from paths
V1_PROMPT_IDS = {path.replace("/", ".").removesuffix(".md") for path in V1_PROMPT_PATHS}

# Validation patterns
_OWNER_PATTERN = re.compile(r"^@[\w.\-]+(/[\w.\-]+)?$")
_RFC3339_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$")


@dataclass
class MetadataIssue:
    """A single metadata validation issue."""

    prompt_path: str
    field: str
    code: str
    message: str
    is_error: bool  # True if hard failure, False if warning


@dataclass
class MetadataValidationResult:
    """Result of validating metadata across all v1 prompts."""

    ok: bool
    issues: list[MetadataIssue] = field(default_factory=list)
    prompts_checked: int = 0


def _parse_metadata_block(content: str) -> dict[str, str]:
    """Extract metadata from YAML-like comment block at top of markdown.

    Looks for HTML comments of the form:
    <!-- owner: @user -->
    <!-- last_reviewed: 2026-02-10T00:00:00Z -->
    <!-- depends_on: [meta.scoring_rubric] -->
    <!-- adjacent_prompts: [architecture/mcp_architecture.md] -->

    Also supports a YAML frontmatter block (---...---).
    """
    metadata: dict[str, str] = {}

    # Try HTML comment metadata
    comment_pattern = re.compile(r"<!--\s*([\w-]+)\s*:\s*(.+?)\s*-->")
    for match in comment_pattern.finditer(content):
        key = match.group(1)
        value = match.group(2).strip()
        metadata[key] = value

    # Try YAML frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            frontmatter = content[3:end]
            for line in frontmatter.splitlines():
                line = line.strip()
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip()
                    value = value.strip()
                    if key and value:
                        metadata[key] = value

    return metadata


def _parse_list_field(value: str) -> list[str]:
    """Parse a bracket-delimited list field like '[a, b, c]'."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"').strip("'") for item in inner.split(",")]
    return [value]


def _validate_owner(value: str) -> str | None:
    """Validate owner field matches @user or @org/team pattern."""
    if not _OWNER_PATTERN.match(value):
        return f"owner '{value}' does not match @user or @org/team format"
    return None


def _validate_last_reviewed(value: str) -> str | None:
    """Validate last_reviewed is RFC3339 UTC datetime."""
    if not _RFC3339_PATTERN.match(value):
        return f"last_reviewed '{value}' is not valid RFC3339 UTC datetime"
    return None


def _validate_depends_on(value: str) -> str | None:
    """Validate depends_on references exist in v1 prompt ID registry."""
    ids = _parse_list_field(value)
    for prompt_id in ids:
        if prompt_id and prompt_id not in V1_PROMPT_IDS:
            return f"depends_on references unknown prompt_id: '{prompt_id}'"
    return None


def _validate_adjacent_prompts(value: str) -> str | None:
    """Validate adjacent_prompts are canonical prompt_path values."""
    paths = _parse_list_field(value)
    for path in paths:
        if path and path not in V1_PROMPT_PATHS:
            return f"adjacent_prompts references unknown path: '{path}'"
    return None


_FIELD_VALIDATORS: dict[str, Callable[[str], str | None]] = {
    "owner": _validate_owner,
    "last_reviewed": _validate_last_reviewed,
    "depends_on": _validate_depends_on,
    "adjacent_prompts": _validate_adjacent_prompts,
}


def validate_prompt_metadata(
    prompts_dir: str | Path,
    *,
    now_utc: datetime | None = None,
) -> MetadataValidationResult:
    """Validate metadata on all v1 prompt files.

    Args:
        prompts_dir: Path to the dev/prompts directory.
        now_utc: Current time for cutover enforcement. Defaults to now.

    Returns:
        MetadataValidationResult with issues and pass/fail status.
    """
    now = now_utc or datetime.now(UTC)
    is_enforcing = now >= METADATA_CUTOVER
    prompts_dir = Path(prompts_dir)
    issues: list[MetadataIssue] = []
    prompts_checked = 0

    for prompt_path in V1_PROMPT_PATHS:
        full_path = prompts_dir / prompt_path
        prompts_checked += 1

        if not full_path.exists():
            issues.append(
                MetadataIssue(
                    prompt_path=prompt_path,
                    field="file",
                    code="missing_prompt_file",
                    message=f"v1 prompt file not found: {prompt_path}",
                    is_error=is_enforcing,
                )
            )
            continue

        content = full_path.read_text(encoding="utf-8")
        metadata = _parse_metadata_block(content)

        for required_field in sorted(REQUIRED_METADATA_FIELDS):
            if required_field not in metadata:
                issues.append(
                    MetadataIssue(
                        prompt_path=prompt_path,
                        field=required_field,
                        code="missing_metadata_field",
                        message=f"missing required metadata field '{required_field}' "
                        f"in {prompt_path}",
                        is_error=is_enforcing,
                    )
                )
            else:
                validator = _FIELD_VALIDATORS.get(required_field)
                if validator:
                    error = validator(metadata[required_field])
                    if error:
                        issues.append(
                            MetadataIssue(
                                prompt_path=prompt_path,
                                field=required_field,
                                code="invalid_metadata_field",
                                message=f"{error} in {prompt_path}",
                                is_error=is_enforcing,
                            )
                        )

    has_errors = any(issue.is_error for issue in issues)
    return MetadataValidationResult(
        ok=not has_errors,
        issues=issues,
        prompts_checked=prompts_checked,
    )
