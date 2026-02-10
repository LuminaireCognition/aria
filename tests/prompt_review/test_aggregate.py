import json
from datetime import datetime, timezone

from aria_esi.prompt_review.aggregate import aggregate_combined_results


def _base_combined() -> dict:
    return {
        "schema_version": "v1",
        "run_context": {
            "event": "pull_request",
            "base_sha": "a",
            "head_sha": "b",
            "ref": "refs/pull/1/head",
            "pr_number": 1,
            "generated_at_utc": "2026-02-09T00:00:00Z",
        },
        "matcher": {
            "changed_files": ["src/aria_esi/mcp/server.py"],
            "case_sensitive": True,
            "rename_mode": "old_and_new",
            "delete_mode": "include_deleted_path",
            "mode": "normal",
            "error_code": None,
            "unmatched_files": [],
            "matched_rules": ["foundation.core_surfaces.v1"],
            "before_missing_fallback": None,
        },
        "prompts": [
            {
                "prompt_id": "testing.test_harness",
                "prompt_instance_id": "testing.test_harness@default",
                "prompt_path": "testing/test_harness.md",
                "tier": "foundation",
                "selection_reason": "foundation_trigger",
                "selection_trace": [
                    {
                        "tier": "foundation",
                        "selection_reason": "foundation_trigger",
                        "matched_by": "rule_id",
                        "rule_id": "foundation.core_surfaces.v1",
                    }
                ],
                "status": "success",
                "not_applicable_reason": None,
                "duration_ms": 20,
                "findings": [],
            }
        ],
        "summary": {
            "by_severity": {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0},
            "by_state": {"unresolved": 0, "resolved": 0, "waived": 0},
            "total_findings": 0,
            "total_prompts": 1,
        },
        "gate_decision": "pass",
    }


def test_output_schema_v1_rejects_missing_required_fields(tmp_path):
    combined = _base_combined()
    del combined["summary"]

    path = tmp_path / "combined.json"
    path.write_text(json.dumps(combined))

    result = aggregate_combined_results(path)
    assert result.gate_decision == "fail"
    assert any(issue.code == "schema_error" for issue in result.issues)


def test_parser_fails_closed_on_missing_combined_artifact(tmp_path):
    missing = tmp_path / "missing.json"
    result = aggregate_combined_results(missing)
    assert result.gate_decision == "fail"
    assert result.issues[0].code == "missing_artifact"


def test_duplicate_prompt_instance_finding_tuple_uses_highest_severity(tmp_path):
    combined = _base_combined()
    combined["prompts"][0]["findings"] = [
        {
            "finding_id": "F-1",
            "severity": "Medium",
            "state": "unresolved",
            "summary": "first",
            "file_refs": ["a.py"],
            "waiver_id": None,
        },
        {
            "finding_id": "F-1",
            "severity": "High",
            "state": "unresolved",
            "summary": "second",
            "file_refs": ["a.py"],
            "waiver_id": "W-1",
        },
    ]

    path = tmp_path / "combined.json"
    path.write_text(json.dumps(combined))
    result = aggregate_combined_results(path)

    findings = result.normalized["prompts"][0]["findings"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "High"
    assert result.requires_high_waiver_check is True


def test_schema_cutover_enforces_full_compliance_at_cutover(tmp_path):
    combined = _base_combined()
    del combined["prompts"][0]["prompt_instance_id"]

    path = tmp_path / "combined.json"
    path.write_text(json.dumps(combined))

    before = aggregate_combined_results(path, now_utc=datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc))
    assert before.gate_decision == "pass"
    assert any("adapter_recoverable" in issue.code for issue in before.issues)

    after = aggregate_combined_results(path, now_utc=datetime(2026, 3, 31, 0, 0, tzinfo=timezone.utc))
    assert after.gate_decision == "fail"
    assert any(issue.code == "schema_error" for issue in after.issues)


def test_pr_missing_shas_emits_deterministic_failure_artifact_contract(tmp_path):
    combined = _base_combined()
    combined["matcher"]["mode"] = "fail_closed"
    combined["matcher"]["error_code"] = "missing_or_unfetchable_shas"
    combined["prompts"] = []
    combined["summary"]["total_prompts"] = 0

    path = tmp_path / "combined.json"
    path.write_text(json.dumps(combined))
    result = aggregate_combined_results(path)
    assert result.gate_decision == "fail"
    assert result.normalized["matcher"]["mode"] == "fail_closed"
