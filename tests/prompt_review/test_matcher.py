from aria_esi.prompt_review.matcher import select_prompts


def test_matcher_dedups_same_prompt_across_tiers(tmp_path):
    changed = tmp_path / "changed.txt"
    changed.write_text("src/aria_esi/mcp/server.py\n")

    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=changed.read_text().splitlines(),
    )

    selected_paths = [item["prompt_path"] for item in result["selected"]]
    assert selected_paths.count("security/audit_ai.md") == 1
    entry = next(item for item in result["selected"] if item["prompt_path"] == "security/audit_ai.md")
    assert entry["selection_trace"]


def test_deferred_prompt_match_maps_to_deferred_fallback():
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["src/aria_esi/services/navigation/router.py"],
    )

    assert any(item["status"] == "skipped_deferred" for item in result["skipped_deferred"])
    # Fallback can be selected then deduped away by higher-tier precedence.
    assert all(p["tier"] != "fallback" for p in result["selected"])
    assert result["matched_rules"]


def test_multiple_proposals_get_unique_prompt_instance_id():
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["dev/proposals/ONE.md", "dev/proposals/TWO.md"],
        proposal_paths=["dev/proposals/ONE.md", "dev/proposals/TWO.md"],
    )

    gate_instances = [
        item["prompt_instance_id"]
        for item in result["selected"]
        if item["prompt_path"] == "dev/proposal_implementation_readiness.md"
    ]
    assert len(gate_instances) == 2
    assert len(set(gate_instances)) == 2


def test_postmerge_gate_prompt_only_when_applicable():
    negative = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="push",
        changed_files=["src/aria_esi/core/config.py"],
        postmerge_applicable=False,
    )
    assert all(p["prompt_path"] != "dev/postmerge_regression_audit.md" for p in negative["selected"])

    positive = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="push",
        changed_files=["src/aria_esi/core/config.py"],
        postmerge_applicable=True,
    )
    assert any(p["prompt_path"] == "dev/postmerge_regression_audit.md" for p in positive["selected"])


def test_matcher_output_includes_unmatched_files_and_mode_schema_valid():
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["random/file.txt", "src/aria_esi/mcp/server.py"],
    )
    assert result["mode"] == "normal"
    assert result["error_code"] is None
    assert "random/file.txt" in result["unmatched_files"]


def test_selection_trace_uses_canonical_rule_id_catalog():
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["src/aria_esi/mcp/server.py"],
    )
    traces = [trace for prompt in result["selected"] for trace in prompt["selection_trace"]]
    for trace in traces:
        if trace["matched_by"] == "rule_id":
            assert isinstance(trace["rule_id"], str)
            assert trace["rule_id"].endswith(".v1")


def test_registry_includes_proposal_readiness_gate_prompt_id():
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["dev/proposals/PROMPT_LIBRARY_REVIEW_COVERAGE_PROPOSAL.md"],
        proposal_paths=["dev/proposals/PROMPT_LIBRARY_REVIEW_COVERAGE_PROPOSAL.md"],
    )
    proposal_gate = next(
        prompt for prompt in result["selected"] if prompt["prompt_path"] == "dev/proposal_implementation_readiness.md"
    )
    assert proposal_gate["prompt_id"] == "dev.proposal_implementation_readiness"


def test_required_gate_prompts_not_suppressed_by_non_v1_ignore_rule():
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["dev/proposals/EXAMPLE.md"],
        proposal_paths=["dev/proposals/EXAMPLE.md"],
    )
    assert any(prompt["prompt_path"] == "dev/proposal_implementation_readiness.md" for prompt in result["selected"])
