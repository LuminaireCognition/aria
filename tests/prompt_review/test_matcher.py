import yaml

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


def test_matcher_selects_foundation_on_src_change():
    """#1: Any change under src/ triggers foundation prompts."""
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["src/aria_esi/core/config.py"],
    )
    selected_paths = [p["prompt_path"] for p in result["selected"]]
    assert "security/audit_ai.md" in selected_paths
    assert "testing/test_harness.md" in selected_paths
    # Verify foundation trigger
    foundation = [p for p in result["selected"] if p["tier"] == "foundation"]
    assert len(foundation) > 0


def test_matcher_case_sensitive_paths():
    """#2: Path matching is case-sensitive per config."""
    result_lower = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["src/aria_esi/mcp/server.py"],
    )
    result_upper = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["SRC/ARIA_ESI/MCP/SERVER.PY"],
    )
    # Uppercase should not match any deep-dive triggers
    lower_deep = [p for p in result_lower["selected"] if p["tier"] == "deep_dive"]
    upper_deep = [p for p in result_upper["selected"] if p["tier"] == "deep_dive"]
    assert len(lower_deep) > 0
    assert len(upper_deep) == 0


def test_matcher_rename_uses_old_and_new_paths():
    """#3: Both old and new paths are considered for renames."""
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["src/aria_esi/old_module.py", "src/aria_esi/new_module.py"],
    )
    # Both paths should be in changed_files
    assert "src/aria_esi/old_module.py" in result["changed_files"]
    assert "src/aria_esi/new_module.py" in result["changed_files"]


def test_matcher_delete_includes_deleted_path():
    """#4: Deleted files are included in changed_files matching."""
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["src/aria_esi/deleted_module.py"],
    )
    assert "src/aria_esi/deleted_module.py" in result["changed_files"]
    # Should trigger foundation since src/** matches
    foundation = [p for p in result["selected"] if p["tier"] == "foundation"]
    assert len(foundation) > 0


def test_no_deep_dive_match_uses_global_fallback():
    """#7: When no deep-dive rule matches and no deferred hit, fallback is used."""
    # Use a file that triggers NO foundation or deep-dive rules, forcing pure fallback
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["random_unmatched_file.txt"],
    )
    # No rules match, so fallback is the only source of foundation-type prompts
    fallback = [p for p in result["selected"] if p["tier"] == "fallback"]
    assert len(fallback) > 0


def test_gate_prompt_uses_gate_trigger_selection_reason():
    """#11: Gate prompts have selection_reason=gate_trigger."""
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["src/aria_esi/core/config.py"],
    )
    gate = [p for p in result["selected"] if p["tier"] == "gate"]
    for g in gate:
        assert g["selection_reason"] in {"gate_trigger", "postmerge_policy"}


def test_prompt_id_registry_is_fixed_for_v1_paths():
    """#27: Prompt IDs derive deterministically from paths."""
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["src/aria_esi/mcp/server.py"],
    )
    for prompt in result["selected"]:
        expected_id = prompt["prompt_path"].replace("/", ".").removesuffix(".md")
        assert prompt["prompt_id"] == expected_id


def test_prompt_path_namespace_is_canonical_end_to_end():
    """#39: All prompt paths use canonical forward-slash POSIX format."""
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["src/aria_esi/mcp/server.py"],
    )
    for prompt in result["selected"]:
        assert "\\" not in prompt["prompt_path"]
        assert not prompt["prompt_path"].startswith("/")
        assert ".." not in prompt["prompt_path"]


def test_matcher_overlap_union_then_dedup():
    """#5: File matching both foundation and deep-dive triggers produces deduplicated selection."""
    # src/aria_esi/mcp/server.py matches both src/** (foundation) and src/aria_esi/mcp/** (deep_dive)
    # security/audit_ai.md appears in both foundation prompt_paths and fallback prompt_paths
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["src/aria_esi/mcp/server.py"],
    )
    selected_paths = [p["prompt_path"] for p in result["selected"]]
    # audit_ai appears in foundation and fallback — should be deduped to one entry
    assert selected_paths.count("security/audit_ai.md") == 1
    # The winning entry should be at the higher-precedence tier (foundation < fallback)
    audit = next(p for p in result["selected"] if p["prompt_path"] == "security/audit_ai.md")
    assert audit["tier"] == "foundation"


def test_overlap_executes_once_and_preserves_selection_trace():
    """#25: File triggers prompt via both foundation AND fallback; single selection with merged trace."""
    # src/aria_esi/core/config.py triggers:
    #   - foundation (src/**) → includes security/audit_ai.md
    #   - deferred deep_dive (src/aria_esi/core/**) → triggers fallback → also includes security/audit_ai.md
    # Result: audit_ai appears from both tiers, gets deduped with merged trace
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["src/aria_esi/core/config.py"],
    )
    audit = next(p for p in result["selected"] if p["prompt_path"] == "security/audit_ai.md")
    # Should appear exactly once
    audit_count = sum(1 for p in result["selected"] if p["prompt_path"] == "security/audit_ai.md")
    assert audit_count == 1
    # Should have merged selection_trace with entries from both foundation and fallback tiers
    trace_tiers = {entry["tier"] for entry in audit["selection_trace"]}
    assert len(trace_tiers) >= 2, f"Expected merged trace from multiple tiers, got: {trace_tiers}"


def test_prompt_instance_id_normalization_canonical_repo_relative():
    """#26: prompt_instance_id follows canonical format; prompt_path is library-relative."""
    result = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event="pull_request",
        changed_files=["src/aria_esi/core/config.py"],
        proposal_paths=["dev/proposals/EXAMPLE.md"],
    )
    for prompt in result["selected"]:
        # prompt_path should not have dev/prompts/ prefix
        assert not prompt["prompt_path"].startswith("dev/prompts/"), (
            f"prompt_path should be library-relative: {prompt['prompt_path']}"
        )
        if prompt["prompt_path"] == "dev/proposal_implementation_readiness.md":
            # Proposal fan-out: <prompt_id>@proposal:<encoded_path>
            assert "@proposal:" in prompt["prompt_instance_id"]
        else:
            # Non-proposal: <prompt_id>@default
            assert prompt["prompt_instance_id"].endswith("@default"), (
                f"Expected @default suffix: {prompt['prompt_instance_id']}"
            )
            expected_id = prompt["prompt_path"].replace("/", ".").removesuffix(".md")
            assert prompt["prompt_instance_id"] == f"{expected_id}@default"


def test_duplicate_rule_id_fails_closed_at_startup(tmp_path):
    """#45: Duplicate rule_ids in config cause deterministic behavior."""
    config = {
        "version": "v1",
        "engine": "gitwildmatch",
        "case_sensitive": True,
        "rename_mode": "old_and_new",
        "delete_mode": "include_deleted_path",
        "foundation": {
            "rule_id": "foundation.core_surfaces.v1",
            "prompt_paths": ["security/audit_ai.md"],
            "triggers": ["src/**"],
        },
        "deep_dive": [
            {
                "rule_id": "deep_dive.dup.v1",
                "prompt_path": "architecture/mcp_architecture.md",
                "deferred": False,
                "triggers": ["src/mcp/**"],
            },
            {
                "rule_id": "deep_dive.dup.v1",  # Duplicate!
                "prompt_path": "testing/coverage_quality.md",
                "deferred": False,
                "triggers": ["tests/**"],
            },
        ],
        "gate": {"rules": []},
        "fallback": {
            "pull_request": {
                "rule_id": "fallback.pull_request.v1",
                "prompt_paths": ["security/audit_ai.md"],
            },
        },
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))
    result = select_prompts(
        config_path=str(config_path),
        event="pull_request",
        changed_files=["src/mcp/server.py", "tests/test_foo.py"],
    )
    assert result["mode"] == "fail_closed"
    assert result["error_code"] == "duplicate_rule_id"
    assert result["selected"] == []
