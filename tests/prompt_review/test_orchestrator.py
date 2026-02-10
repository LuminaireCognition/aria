"""Tests for the prompt review orchestrator (post-execution coverage auditor)."""

from aria_esi.prompt_review.orchestrator import run_orchestrator_check


def _make_prompt(prompt_id, prompt_path, status="success", findings=None, tier="foundation"):
    return {
        "prompt_id": prompt_id,
        "prompt_instance_id": f"{prompt_id}@default",
        "prompt_path": prompt_path,
        "tier": tier,
        "selection_reason": "foundation_trigger",
        "selection_trace": [
            {
                "tier": tier,
                "selection_reason": "foundation_trigger",
                "matched_by": "rule_id",
                "rule_id": "foundation.core_surfaces.v1",
            }
        ],
        "status": status,
        "not_applicable_reason": None,
        "duration_ms": 10,
        "findings": findings or [],
    }


def _make_finding(finding_id, severity="Medium", file_refs=None):
    return {
        "finding_id": finding_id,
        "severity": severity,
        "state": "unresolved",
        "summary": f"Test finding {finding_id}",
        "file_refs": file_refs or [],
        "waiver_id": None,
    }


def test_orchestrator_executes_after_all_other_prompt_tiers():
    """#47: Orchestrator consumes results from all tiers and produces its own findings."""
    combined = {
        "foundation": [
            _make_prompt("security.audit_ai", "security/audit_ai.md", findings=[
                _make_finding("F-1", file_refs=["src/server.py"]),
            ]),
        ],
        "deep_dive": [
            _make_prompt("architecture.mcp_architecture", "architecture/mcp_architecture.md",
                         tier="deep_dive", findings=[
                _make_finding("F-2", file_refs=["src/mcp/server.py"]),
            ]),
        ],
        "gate": [
            _make_prompt("dev.premerge", "dev/premerge.md", tier="gate", findings=[]),
        ],
        "matcher": {
            "changed_files": ["src/server.py", "src/mcp/server.py"],
            "unmatched_files": [],
            "matched_rules": ["foundation.core_surfaces.v1"],
        },
    }
    result = run_orchestrator_check(combined)
    assert result["prompt_id"] == "meta.review_orchestrator"
    assert result["tier"] == "foundation"
    assert result["status"] == "success"


def test_orchestrator_flags_unmatched_changed_files_as_coverage_gap():
    """#48: Unmatched files not referenced by any finding are flagged."""
    combined = {
        "foundation": [
            _make_prompt("security.audit_ai", "security/audit_ai.md", findings=[
                _make_finding("F-1", file_refs=["src/known.py"]),
            ]),
        ],
        "deep_dive": [],
        "gate": [],
        "matcher": {
            "changed_files": ["src/known.py", "src/orphan.py"],
            "unmatched_files": ["src/orphan.py"],
            "matched_rules": ["foundation.core_surfaces.v1"],
        },
    }
    result = run_orchestrator_check(combined)
    coverage_gaps = [f for f in result["findings"] if "Coverage gap" in f["summary"]]
    assert len(coverage_gaps) >= 1
    assert any("src/orphan.py" in f["summary"] for f in coverage_gaps)


def test_orchestrator_does_not_produce_facet_specific_findings():
    """#49: Orchestrator must not produce code quality or security findings."""
    combined = {
        "foundation": [
            _make_prompt("security.audit_ai", "security/audit_ai.md", findings=[
                _make_finding("F-1", severity="Critical", file_refs=["src/vuln.py"]),
            ]),
        ],
        "deep_dive": [],
        "gate": [],
        "matcher": {
            "changed_files": ["src/vuln.py"],
            "unmatched_files": [],
            "matched_rules": ["foundation.core_surfaces.v1"],
        },
    }
    result = run_orchestrator_check(combined)
    # Orchestrator should only produce meta-level findings, not re-emit facet findings
    for finding in result["findings"]:
        assert finding["finding_id"].startswith("ORCH-")
        # Should not contain facet-specific language
        summary_lower = finding["summary"].lower()
        assert "vulnerability" not in summary_lower
        assert "injection" not in summary_lower


def test_orchestrator_emits_info_finding_when_all_inputs_skipped():
    """#50: When all prompts are skipped, emit a single Info finding."""
    combined = {
        "foundation": [
            _make_prompt("security.audit_ai", "security/audit_ai.md",
                         status="skipped_not_applicable"),
        ],
        "deep_dive": [
            _make_prompt("testing.coverage_quality", "testing/coverage_quality.md",
                         status="skipped_deferred", tier="deep_dive"),
        ],
        "gate": [
            _make_prompt("dev.premerge", "dev/premerge.md",
                         status="skipped_not_applicable", tier="gate"),
        ],
        "matcher": {
            "changed_files": [],
            "unmatched_files": [],
            "matched_rules": [],
        },
    }
    result = run_orchestrator_check(combined)
    assert len(result["findings"]) == 1
    assert result["findings"][0]["severity"] == "Info"
    assert "no prompt results" in result["findings"][0]["summary"].lower()


def test_orchestrator_detects_cross_prompt_contradictory_findings():
    """#51: Contradictory severity on same file from different prompts is flagged."""
    combined = {
        "foundation": [
            _make_prompt("security.audit_ai", "security/audit_ai.md", findings=[
                _make_finding("F-1", severity="Critical", file_refs=["src/shared.py"]),
            ]),
            _make_prompt("testing.test_harness", "testing/test_harness.md", findings=[
                _make_finding("F-2", severity="Low", file_refs=["src/shared.py"]),
            ]),
        ],
        "deep_dive": [],
        "gate": [],
        "matcher": {
            "changed_files": ["src/shared.py"],
            "unmatched_files": [],
            "matched_rules": ["foundation.core_surfaces.v1"],
        },
    }
    result = run_orchestrator_check(combined)
    conflicts = [f for f in result["findings"] if "Cross-prompt conflict" in f["summary"]]
    assert len(conflicts) >= 1
    assert any("src/shared.py" in f["summary"] for f in conflicts)
