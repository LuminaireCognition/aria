from __future__ import annotations

import json
from datetime import datetime, timezone
from fnmatch import fnmatchcase

import yaml

from .models import ValidationIssue, WaiverValidationResult

REQUIRED_WAIVER_FIELDS = {
    "waiver_id",
    "severity",
    "finding_id",
    "prompt_id",
    "paths",
    "approved_by",
    "owner",
    "follow_up_issue",
    "created_on",
    "expires_on",
    "status",
}


def _parse_date(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _path_match(path: str, pattern: str) -> bool:
    return fnmatchcase(path, pattern)


def _parse_codeowners(codeowners_text: str) -> list[tuple[str, list[str]]]:
    rules: list[tuple[str, list[str]]] = []
    for raw_line in codeowners_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0].lstrip("/")
        owners = [p for p in parts[1:] if p.startswith("@")]
        rules.append((pattern, owners))
    return rules


def _resolved_code_owner(path: str, rules: list[tuple[str, list[str]]]) -> str | None:
    selected: list[str] | None = None
    for pattern, owners in rules:
        if _path_match(path, pattern):
            selected = owners
    if not selected:
        return None
    return selected[0]


def validate_high_waivers(
    *,
    combined_json_path: str,
    waiver_yaml_path: str,
    codeowners_path: str,
    now_utc: datetime | None = None,
) -> WaiverValidationResult:
    now = now_utc or datetime.now(timezone.utc)
    issues: list[ValidationIssue] = []

    try:
        with open(combined_json_path, encoding="utf-8") as fh:
            combined = json.load(fh)
    except FileNotFoundError as exc:
        return WaiverValidationResult(
            ok=False, issues=[ValidationIssue("missing_combined", str(exc))]
        )

    unresolved_high: list[dict] = []
    changed_files = set(combined.get("matcher", {}).get("changed_files", []))
    for prompt in combined.get("prompts", []):
        prompt_id = prompt.get("prompt_id")
        for finding in prompt.get("findings", []):
            if finding.get("severity") == "High" and finding.get("state") == "unresolved":
                unresolved_high.append(
                    {
                        "prompt_id": prompt_id,
                        "finding_id": finding.get("finding_id"),
                        "file_refs": finding.get("file_refs", []),
                    }
                )

    if not unresolved_high:
        return WaiverValidationResult(ok=True, issues=[])

    try:
        with open(waiver_yaml_path, encoding="utf-8") as fh:
            waiver_doc = yaml.safe_load(fh) or {}
    except FileNotFoundError as exc:
        return WaiverValidationResult(
            ok=False, issues=[ValidationIssue("missing_waiver_file", str(exc))]
        )

    waivers = waiver_doc.get("waivers", [])
    if not isinstance(waivers, list):
        return WaiverValidationResult(
            ok=False, issues=[ValidationIssue("invalid_waiver_schema", "waivers must be list")]
        )

    try:
        with open(codeowners_path, encoding="utf-8") as fh:
            codeowners_rules = _parse_codeowners(fh.read())
    except FileNotFoundError as exc:
        return WaiverValidationResult(
            ok=False, issues=[ValidationIssue("missing_codeowners", str(exc))]
        )

    waiver_lookup: dict[tuple[str, str], dict] = {}
    for waiver in waivers:
        missing = REQUIRED_WAIVER_FIELDS - set(waiver.keys())
        if missing:
            issues.append(
                ValidationIssue(
                    "waiver_missing_fields",
                    f"waiver {waiver.get('waiver_id', 'unknown')} missing {sorted(missing)}",
                )
            )
            continue

        if waiver["severity"] != "High":
            issues.append(
                ValidationIssue(
                    "waiver_invalid_severity", f"{waiver['waiver_id']} severity != High"
                )
            )
            continue

        if _parse_date(waiver["expires_on"]) < now:
            issues.append(ValidationIssue("waiver_expired", waiver["waiver_id"]))
            continue

        if not (isinstance(waiver["approved_by"], list) and len(waiver["approved_by"]) >= 2):
            issues.append(ValidationIssue("waiver_insufficient_approvals", waiver["waiver_id"]))
            continue

        if waiver["owner"] not in waiver["approved_by"]:
            issues.append(
                ValidationIssue("waiver_missing_prompt_owner_approval", waiver["waiver_id"])
            )
            continue

        for path in waiver["paths"]:
            resolved = _resolved_code_owner(path, codeowners_rules)
            if resolved is None:
                issues.append(
                    ValidationIssue("waiver_no_codeowner_match", f"{waiver['waiver_id']}:{path}")
                )
                continue
            if resolved not in waiver["approved_by"]:
                issues.append(
                    ValidationIssue(
                        "waiver_missing_codeowner_approval", f"{waiver['waiver_id']}:{path}"
                    )
                )

        if not any(
            any(_path_match(changed, p) for p in waiver["paths"]) for changed in changed_files
        ):
            issues.append(ValidationIssue("waiver_path_mismatch", waiver["waiver_id"]))
            continue

        key = (waiver["prompt_id"], waiver["finding_id"])
        waiver_lookup[key] = waiver

    for finding in unresolved_high:
        key = (finding["prompt_id"], finding["finding_id"])
        if key not in waiver_lookup:
            issues.append(
                ValidationIssue(
                    "unwaived_high",
                    f"missing waiver for prompt_id={finding['prompt_id']} finding_id={finding['finding_id']}",
                )
            )

    return WaiverValidationResult(ok=not issues, issues=issues)
