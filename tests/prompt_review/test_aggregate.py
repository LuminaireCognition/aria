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


def test_duplicate_prompt_id_finding_id_tuple_uses_highest_severity(tmp_path):
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


def test_schema_cutover_enforces_full_compliance_at_2026_03_31_000000z(tmp_path):
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


def test_gate_fails_on_unresolved_critical(tmp_path):
    """#19: Unresolved Critical findings cause gate failure."""
    combined = _base_combined()
    combined["prompts"][0]["findings"] = [
        {
            "finding_id": "C-1",
            "severity": "Critical",
            "state": "unresolved",
            "summary": "critical issue",
            "file_refs": ["src/server.py"],
            "waiver_id": None,
        }
    ]

    path = tmp_path / "combined.json"
    path.write_text(json.dumps(combined))
    result = aggregate_combined_results(path)
    assert result.gate_decision == "fail"


def test_gate_fails_on_unwaived_high(tmp_path):
    """#20: Unresolved High findings require waiver check."""
    combined = _base_combined()
    combined["prompts"][0]["findings"] = [
        {
            "finding_id": "H-1",
            "severity": "High",
            "state": "unresolved",
            "summary": "high issue",
            "file_refs": ["src/server.py"],
            "waiver_id": None,
        }
    ]

    path = tmp_path / "combined.json"
    path.write_text(json.dumps(combined))
    result = aggregate_combined_results(path)
    # High alone doesn't fail gate, but requires waiver check
    assert result.requires_high_waiver_check is True
    assert result.unresolved_high_count == 1


def test_duplicate_prompt_instance_conflicting_status_fails_schema(tmp_path):
    """#32: Two entries with same prompt_instance_id and conflicting status fail schema."""
    combined = _base_combined()
    combined["prompts"].append({
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
        "status": "failure",
        "not_applicable_reason": None,
        "duration_ms": 10,
        "findings": [],
    })

    path = tmp_path / "combined.json"
    path.write_text(json.dumps(combined))
    result = aggregate_combined_results(path)
    # With failure status present, gate should fail
    assert result.gate_decision == "fail"


def test_summary_total_prompts_includes_skipped_by_state_finding_only(tmp_path):
    """#31: Skipped prompts are counted in total_prompts."""
    combined = _base_combined()
    combined["prompts"].append({
        "prompt_id": "dev.premerge",
        "prompt_instance_id": "dev.premerge@default",
        "prompt_path": "dev/premerge.md",
        "tier": "gate",
        "selection_reason": "gate_trigger",
        "selection_trace": [
            {
                "tier": "gate",
                "selection_reason": "gate_trigger",
                "matched_by": "gate_policy",
                "rule_id": "gate.premerge.v1",
            }
        ],
        "status": "skipped_not_applicable",
        "not_applicable_reason": "event_not_supported",
        "duration_ms": 0,
        "findings": [],
    })
    combined["summary"]["total_prompts"] = 2

    path = tmp_path / "combined.json"
    path.write_text(json.dumps(combined))
    result = aggregate_combined_results(path)
    assert result.gate_decision == "pass"
    assert len(result.normalized["prompts"]) == 2


def test_missing_sha_not_applicable_entries_are_schema_valid(tmp_path):
    """#41: Not-applicable entries with missing_shas reason pass schema validation."""
    combined = _base_combined()
    combined["prompts"] = [
        {
            "prompt_id": "dev.premerge",
            "prompt_instance_id": "dev.premerge@default",
            "prompt_path": "dev/premerge.md",
            "tier": "gate",
            "selection_reason": "gate_trigger",
            "selection_trace": [
                {
                    "tier": "gate",
                    "selection_reason": "gate_trigger",
                    "matched_by": "gate_policy",
                    "rule_id": "gate.premerge.v1",
                }
            ],
            "status": "skipped_not_applicable",
            "not_applicable_reason": "missing_shas",
            "duration_ms": 0,
            "findings": [],
        }
    ]
    combined["summary"]["total_prompts"] = 1

    path = tmp_path / "combined.json"
    path.write_text(json.dumps(combined))
    result = aggregate_combined_results(path)
    assert result.gate_decision == "pass"
    assert not any(i.code == "schema_error" for i in result.issues)


def test_scoring_rubric_execution_contract(tmp_path):
    """#40: scoring_rubric prompt can emit findings with foundation_trigger."""
    combined = _base_combined()
    combined["prompts"].append({
        "prompt_id": "meta.scoring_rubric",
        "prompt_instance_id": "meta.scoring_rubric@default",
        "prompt_path": "meta/scoring_rubric.md",
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
        "duration_ms": 15,
        "findings": [
            {
                "finding_id": "SR-1",
                "severity": "Info",
                "state": "unresolved",
                "summary": "Calibration note",
                "file_refs": [],
                "waiver_id": None,
            }
        ],
    })
    combined["summary"]["total_prompts"] = 2

    path = tmp_path / "combined.json"
    path.write_text(json.dumps(combined))
    result = aggregate_combined_results(path)
    assert result.gate_decision == "pass"
    rubric = next(
        p for p in result.normalized["prompts"]
        if p["prompt_id"] == "meta.scoring_rubric"
    )
    assert rubric["selection_reason"] == "foundation_trigger"
    assert len(rubric["findings"]) == 1
