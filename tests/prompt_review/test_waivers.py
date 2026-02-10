import json
from datetime import datetime, timezone

from aria_esi.prompt_review.waivers import validate_high_waivers


def _combined_with_high(tmp_path):
    combined = {
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
                "prompt_id": "security.audit_ai",
                "prompt_instance_id": "security.audit_ai@default",
                "prompt_path": "security/audit_ai.md",
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
                "duration_ms": 10,
                "findings": [
                    {
                        "finding_id": "H-1",
                        "severity": "High",
                        "state": "unresolved",
                        "summary": "high risk",
                        "file_refs": ["src/aria_esi/mcp/server.py"],
                        "waiver_id": "W-1",
                    }
                ],
            }
        ],
    }
    path = tmp_path / "combined.json"
    path.write_text(json.dumps(combined))
    return path


def _codeowners(tmp_path):
    path = tmp_path / "CODEOWNERS"
    path.write_text("* @org/engineering\nsrc/** @org/devex\n")
    return path


def test_waiver_valid_active_high_allows_merge(tmp_path):
    combined = _combined_with_high(tmp_path)
    codeowners = _codeowners(tmp_path)
    waivers = tmp_path / "waivers.yaml"
    waivers.write_text(
        """
waivers:
  - waiver_id: W-1
    severity: High
    finding_id: H-1
    prompt_id: security.audit_ai
    paths: [src/**]
    approved_by: ["@org/security", "@org/devex"]
    owner: "@org/security"
    follow_up_issue: "#123"
    created_on: "2026-02-09T00:00:00Z"
    expires_on: "2026-02-20T00:00:00Z"
    status: active
"""
    )

    result = validate_high_waivers(
        combined_json_path=str(combined),
        waiver_yaml_path=str(waivers),
        codeowners_path=str(codeowners),
        now_utc=datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc),
    )

    assert result.ok is True


def test_waiver_expired_fails_gate(tmp_path):
    combined = _combined_with_high(tmp_path)
    codeowners = _codeowners(tmp_path)
    waivers = tmp_path / "waivers.yaml"
    waivers.write_text(
        """
waivers:
  - waiver_id: W-1
    severity: High
    finding_id: H-1
    prompt_id: security.audit_ai
    paths: [src/**]
    approved_by: ["@org/security", "@org/devex"]
    owner: "@org/security"
    follow_up_issue: "#123"
    created_on: "2026-02-09T00:00:00Z"
    expires_on: "2026-02-10T00:00:00Z"
    status: active
"""
    )

    result = validate_high_waivers(
        combined_json_path=str(combined),
        waiver_yaml_path=str(waivers),
        codeowners_path=str(codeowners),
        now_utc=datetime(2026, 2, 11, 0, 0, tzinfo=timezone.utc),
    )

    assert result.ok is False
    assert any(issue.code == "waiver_expired" for issue in result.issues)


def test_waiver_path_mismatch_fails_gate(tmp_path):
    combined = _combined_with_high(tmp_path)
    codeowners = _codeowners(tmp_path)
    waivers = tmp_path / "waivers.yaml"
    waivers.write_text(
        """
waivers:
  - waiver_id: W-1
    severity: High
    finding_id: H-1
    prompt_id: security.audit_ai
    paths: [docs/**]
    approved_by: ["@org/security", "@org/engineering"]
    owner: "@org/security"
    follow_up_issue: "#123"
    created_on: "2026-02-09T00:00:00Z"
    expires_on: "2026-02-20T00:00:00Z"
    status: active
"""
    )

    result = validate_high_waivers(
        combined_json_path=str(combined),
        waiver_yaml_path=str(waivers),
        codeowners_path=str(codeowners),
        now_utc=datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc),
    )

    assert result.ok is False
    assert any(issue.code == "waiver_path_mismatch" for issue in result.issues)


def test_dual_role_owner_requires_plus_one_distinct_approver(tmp_path):
    """#30: When owner is also a codeowner, approved_by must have at least 2 entries."""
    combined = _combined_with_high(tmp_path)
    codeowners = _codeowners(tmp_path)
    waivers = tmp_path / "waivers.yaml"
    # Owner is same as codeowner, only 1 approver total = should fail
    waivers.write_text(
        """
waivers:
  - waiver_id: W-1
    severity: High
    finding_id: H-1
    prompt_id: security.audit_ai
    paths: [src/**]
    approved_by: ["@org/devex"]
    owner: "@org/devex"
    follow_up_issue: "#123"
    created_on: "2026-02-09T00:00:00Z"
    expires_on: "2026-02-20T00:00:00Z"
    status: active
"""
    )

    result = validate_high_waivers(
        combined_json_path=str(combined),
        waiver_yaml_path=str(waivers),
        codeowners_path=str(codeowners),
        now_utc=datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc),
    )

    assert result.ok is False
    assert any(issue.code == "waiver_insufficient_approvals" for issue in result.issues)
