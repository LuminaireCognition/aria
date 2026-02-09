from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .models import SEVERITY_RANK, AggregateResult, ValidationIssue

ALLOWED_PROMPT_STATUS = {"success", "failure", "timeout", "skipped_not_applicable", "skipped_deferred"}
ALLOWED_TIERS = {"foundation", "deep_dive", "gate", "fallback"}
ALLOWED_SELECTION_REASONS = {
    "foundation_trigger",
    "deep_dive_trigger",
    "deferred_fallback",
    "global_fallback",
    "gate_trigger",
    "postmerge_policy",
}
ALLOWED_SEVERITY = {"Critical", "High", "Medium", "Low", "Info"}
ALLOWED_STATE = {"unresolved", "resolved", "waived"}
ALLOWED_MATCHER_MODE = {"normal", "before_missing_fallback", "not_applicable", "fail_closed"}
ALLOWED_MATCHER_ERROR_CODE = {None, "missing_or_unfetchable_shas"}
ALLOWED_NOT_APPLICABLE_REASONS = {
    "missing_shas",
    "event_not_supported",
    "non_authoritative_run",
    "missing_pr_linkage",
    "invalid_proposal_path",
    "no_gate_input",
    "invalid_gate_input",
}
ADAPTER_CUTOVER = datetime(2026, 3, 31, 0, 0, 0, tzinfo=UTC)


class SchemaError(ValueError):
    pass


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value).astimezone(UTC)


def _required(obj: dict, key: str):
    if key not in obj:
        raise SchemaError(f"missing required field: {key}")
    return obj[key]


def _sort_prompts(prompts: list[dict]) -> list[dict]:
    tier_rank = {"gate": 0, "deep_dive": 1, "foundation": 2, "fallback": 3}
    return sorted(
        prompts,
        key=lambda p: (tier_rank[p["tier"]], p["prompt_path"], p["prompt_instance_id"]),
    )


def _sort_findings(findings: list[dict]) -> list[dict]:
    return sorted(
        findings,
        key=lambda f: (-SEVERITY_RANK[f["severity"]], f["finding_id"], f["summary"]),
    )


def _normalize_with_adapter(combined: dict, now_utc: datetime, issues: list[ValidationIssue]) -> dict:
    if now_utc >= ADAPTER_CUTOVER:
        return combined

    for prompt in combined.get("prompts", []):
        if "prompt_instance_id" not in prompt and "prompt_id" in prompt:
            prompt["prompt_instance_id"] = f"{prompt['prompt_id']}@default"
            issues.append(
                ValidationIssue(
                    code="adapter_recoverable_missing_prompt_instance_id",
                    message=f"added prompt_instance_id for {prompt.get('prompt_path', 'unknown')}",
                )
            )
    return combined


def _validate_and_normalize_prompt(prompt: dict) -> dict:
    prompt_id = _required(prompt, "prompt_id")
    prompt_instance_id = _required(prompt, "prompt_instance_id")
    prompt_path = _required(prompt, "prompt_path")
    tier = _required(prompt, "tier")
    selection_reason = _required(prompt, "selection_reason")
    status = _required(prompt, "status")
    not_applicable_reason = prompt.get("not_applicable_reason")
    duration_ms = _required(prompt, "duration_ms")
    findings = _required(prompt, "findings")
    selection_trace = _required(prompt, "selection_trace")

    if tier not in ALLOWED_TIERS:
        raise SchemaError(f"invalid tier: {tier}")
    if selection_reason not in ALLOWED_SELECTION_REASONS:
        raise SchemaError(f"invalid selection_reason: {selection_reason}")
    if status not in ALLOWED_PROMPT_STATUS:
        raise SchemaError(f"invalid status: {status}")
    if status == "skipped_not_applicable":
        if not_applicable_reason not in ALLOWED_NOT_APPLICABLE_REASONS:
            raise SchemaError(f"invalid not_applicable_reason: {not_applicable_reason}")
    elif not_applicable_reason is not None:
        raise SchemaError("not_applicable_reason must be null unless status=skipped_not_applicable")
    if not isinstance(duration_ms, int):
        raise SchemaError("duration_ms must be int")
    if not isinstance(findings, list):
        raise SchemaError("findings must be list")
    if not isinstance(selection_trace, list) or not selection_trace:
        raise SchemaError("selection_trace must be non-empty list")
    for trace in selection_trace:
        trace_tier = _required(trace, "tier")
        trace_reason = _required(trace, "selection_reason")
        matched_by = _required(trace, "matched_by")
        rule_id = trace.get("rule_id")
        if trace_tier not in ALLOWED_TIERS:
            raise SchemaError(f"invalid selection_trace tier: {trace_tier}")
        if trace_reason not in ALLOWED_SELECTION_REASONS:
            raise SchemaError(f"invalid selection_trace selection_reason: {trace_reason}")
        if matched_by not in {"rule_id", "gate_policy"}:
            raise SchemaError(f"invalid selection_trace matched_by: {matched_by}")
        if matched_by == "rule_id" and not rule_id:
            raise SchemaError("selection_trace rule_id required when matched_by=rule_id")

    deduped_findings: dict[tuple[str, str], dict] = {}
    for finding in findings:
        finding_id = _required(finding, "finding_id")
        severity = _required(finding, "severity")
        state = _required(finding, "state")
        summary = _required(finding, "summary")
        file_refs = _required(finding, "file_refs")
        waiver_id = finding.get("waiver_id")

        if severity not in ALLOWED_SEVERITY:
            raise SchemaError(f"invalid severity: {severity}")
        if state not in ALLOWED_STATE:
            raise SchemaError(f"invalid state: {state}")
        if not isinstance(file_refs, list):
            raise SchemaError("file_refs must be list")

        normalized = {
            "finding_id": finding_id,
            "severity": severity,
            "state": state,
            "summary": summary,
            "file_refs": sorted(set(file_refs)),
            "waiver_id": waiver_id,
        }
        key = (prompt_instance_id, finding_id)
        existing = deduped_findings.get(key)
        if existing is None or SEVERITY_RANK[severity] > SEVERITY_RANK[existing["severity"]]:
            deduped_findings[key] = normalized

    normalized_findings = _sort_findings(list(deduped_findings.values()))
    return {
        "prompt_id": prompt_id,
        "prompt_instance_id": prompt_instance_id,
        "prompt_path": prompt_path,
        "tier": tier,
        "selection_reason": selection_reason,
        "selection_trace": selection_trace,
        "status": status,
        "not_applicable_reason": not_applicable_reason,
        "duration_ms": duration_ms,
        "findings": normalized_findings,
    }


def aggregate_combined_results(combined_json_path: str | Path, *, now_utc: datetime | None = None) -> AggregateResult:
    now = now_utc or datetime.now(UTC)
    issues: list[ValidationIssue] = []

    try:
        with open(combined_json_path, encoding="utf-8") as fh:
            combined = json.load(fh)
    except FileNotFoundError as exc:
        return AggregateResult(
            gate_decision="fail",
            unresolved_high_count=0,
            requires_high_waiver_check=False,
            normalized={},
            issues=[ValidationIssue(code="missing_artifact", message=str(exc))],
        )
    except json.JSONDecodeError as exc:
        return AggregateResult(
            gate_decision="fail",
            unresolved_high_count=0,
            requires_high_waiver_check=False,
            normalized={},
            issues=[ValidationIssue(code="invalid_json", message=str(exc))],
        )

    try:
        combined = _normalize_with_adapter(combined, now, issues)
        if _required(combined, "schema_version") != "v1":
            raise SchemaError("schema_version must be v1")

        run_context = _required(combined, "run_context")
        generated_at_utc = _required(run_context, "generated_at_utc")
        _parse_timestamp(generated_at_utc)

        matcher = _required(combined, "matcher")
        _required(matcher, "changed_files")
        _required(matcher, "case_sensitive")
        _required(matcher, "rename_mode")
        _required(matcher, "delete_mode")
        matcher_mode = _required(matcher, "mode")
        matcher_error = _required(matcher, "error_code")
        _required(matcher, "unmatched_files")
        _required(matcher, "matched_rules")
        _required(matcher, "before_missing_fallback")
        if matcher_mode not in ALLOWED_MATCHER_MODE:
            raise SchemaError(f"invalid matcher mode: {matcher_mode}")
        if matcher_error not in ALLOWED_MATCHER_ERROR_CODE:
            raise SchemaError(f"invalid matcher error_code: {matcher_error}")

        prompts = _required(combined, "prompts")
        summary = _required(combined, "summary")
        _required(summary, "by_severity")
        _required(summary, "by_state")
        _required(summary, "total_findings")
        _required(summary, "total_prompts")

        if not isinstance(prompts, list):
            raise SchemaError("prompts must be list")

        if (
            matcher_mode == "fail_closed"
            and matcher_error == "missing_or_unfetchable_shas"
            and len(prompts) == 0
        ):
            gate_decision = "fail"
            return AggregateResult(
                gate_decision=gate_decision,
                unresolved_high_count=0,
                requires_high_waiver_check=False,
                normalized={**combined, "gate_decision": gate_decision},
                issues=issues,
            )

        normalized_prompts = [_validate_and_normalize_prompt(prompt) for prompt in prompts]
        normalized_prompts = _sort_prompts(normalized_prompts)

        has_failure = any(p["status"] in {"failure", "timeout"} for p in normalized_prompts)
        unresolved_critical = False
        unresolved_high_count = 0

        for prompt in normalized_prompts:
            for finding in prompt["findings"]:
                if finding["severity"] == "Critical" and finding["state"] != "resolved":
                    unresolved_critical = True
                if finding["severity"] == "High" and finding["state"] == "unresolved":
                    unresolved_high_count += 1

        if has_failure or unresolved_critical:
            gate_decision = "fail"
        else:
            gate_decision = "pass"

        return AggregateResult(
            gate_decision=gate_decision,
            unresolved_high_count=unresolved_high_count,
            requires_high_waiver_check=unresolved_high_count > 0,
            normalized={**combined, "prompts": normalized_prompts, "gate_decision": gate_decision},
            issues=issues,
        )
    except SchemaError as exc:
        return AggregateResult(
            gate_decision="fail",
            unresolved_high_count=0,
            requires_high_waiver_check=False,
            normalized={},
            issues=[*issues, ValidationIssue(code="schema_error", message=str(exc))],
        )
