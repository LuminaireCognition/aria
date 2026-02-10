"""Tests for the prompt review runtime script."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


# Absolute path to the project root for config resolution
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_CONFIG_PATH = str(_PROJECT_ROOT / "dev" / "policy" / "prompt_matcher_rules.yaml")


@pytest.mark.skip(reason="requires post-merge infrastructure — tracking: #21")
def test_postmerge_authoritative_run_tiebreaker_start_time_then_run_id():
    """#28: Post-merge authoritative run tiebreaker uses start_time then run_id.

    Tracking: https://github.com/LuminaireCognition/aria/issues/21
    """


@pytest.mark.skip(reason="requires post-merge infrastructure — tracking: #22")
def test_non_authoritative_postmerge_run_emits_not_applicable_reason():
    """#29: Non-authoritative post-merge run emits not_applicable_reason.

    Tracking: https://github.com/LuminaireCognition/aria/issues/22
    """


@pytest.mark.skip(reason="requires post-merge infrastructure — tracking: #23")
def test_postmerge_status_target_sha_merge_vs_squash_vs_rebase():
    """#36: Post-merge status target SHA differs for merge, squash, and rebase.

    Tracking: https://github.com/LuminaireCognition/aria/issues/23
    """


def _import_runtime():
    """Import the runtime module dynamically."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "prompt_review_runtime",
        str(_PROJECT_ROOT / "dev" / "scripts" / "prompt_review_runtime.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _setup_env(monkeypatch, overrides: dict):
    """Clear runtime env vars and set overrides."""
    for key in list(os.environ.keys()):
        if key.startswith("PROMPT_") or key in {
            "PROPOSAL_PATH", "POSTMERGE_APPLICABLE",
            "POSTMERGE_TARGET_SHA", "PR_NUMBER", "GITHUB_REF",
        }:
            monkeypatch.delenv(key, raising=False)
    # Also clear any GATE_INPUT_ vars
    for key in list(os.environ.keys()):
        if key.startswith("GATE_INPUT_"):
            monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


def test_postmerge_applicability_push_default_branch_required_surfaces(monkeypatch, tmp_path):
    """#14: Push event with postmerge_applicable=True surfaces postmerge prompt."""
    runtime = _import_runtime()
    _setup_env(monkeypatch, {
        "PROMPT_EVENT": "push",
        "PROMPT_BASE_SHA": "abc123",
        "PROMPT_HEAD_SHA": "def456",
        "POSTMERGE_APPLICABLE": "true",
    })

    from aria_esi.prompt_review.matcher import select_prompts
    selected = select_prompts(
        config_path=_CONFIG_PATH,
        event="push",
        changed_files=["src/aria_esi/core/config.py"],
        postmerge_applicable=True,
    )

    with patch.object(runtime, '_git_changed_files', return_value=(["src/aria_esi/core/config.py"], "normal", None, None)):
        with patch.object(runtime, 'select_prompts', return_value=selected):
            monkeypatch.chdir(tmp_path)
            result = runtime.main()

    assert result == 0
    combined = json.loads((tmp_path / "artifacts/prompt-results/combined.json").read_text())
    postmerge = next(
        (p for p in combined["prompts"] if p["prompt_path"] == "dev/postmerge_regression_audit.md"),
        None,
    )
    assert postmerge is not None, "postmerge prompt should be present"
    assert postmerge["prompt_id"] == "dev.postmerge_regression_audit"
    assert postmerge["tier"] == "gate"
    assert postmerge["selection_reason"] == "postmerge_policy"


def test_bootstrap_mode_skips_not_yet_created_v1_prompts_without_failing(monkeypatch, tmp_path):
    """#12: Missing prompt files don't cause runtime failure."""
    runtime = _import_runtime()
    _setup_env(monkeypatch, {
        "PROMPT_EVENT": "pull_request",
        "PROMPT_BASE_SHA": "abc123",
        "PROMPT_HEAD_SHA": "def456",
    })

    def mock_git_changed_files(event, base_sha, head_sha):
        return (["src/aria_esi/mcp/server.py"], "normal", None, None)

    with patch.object(runtime, '_git_changed_files', side_effect=mock_git_changed_files):
        # Patch config path to absolute so it works from any cwd
        with patch.object(runtime, 'select_prompts', wraps=runtime.select_prompts) as mock_select:
            monkeypatch.chdir(tmp_path)
            # Use direct select_prompts mock that uses absolute config path
            from aria_esi.prompt_review.matcher import select_prompts
            selected = select_prompts(
                config_path=_CONFIG_PATH,
                event="pull_request",
                changed_files=["src/aria_esi/mcp/server.py"],
            )
            # Now mock select_prompts in runtime to return our result
            with patch.object(runtime, 'select_prompts', return_value=selected):
                result = runtime.main()

    assert result == 0
    output = tmp_path / "artifacts" / "prompt-results" / "combined.json"
    assert output.exists()
    combined = json.loads(output.read_text())
    assert combined["schema_version"] == "v1"


def test_postmerge_not_applicable_for_non_default_branch_push(monkeypatch, tmp_path):
    """#15: Post-merge prompt not applicable for non-default branch push."""
    runtime = _import_runtime()
    _setup_env(monkeypatch, {
        "PROMPT_EVENT": "push",
        "PROMPT_BASE_SHA": "abc123",
        "PROMPT_HEAD_SHA": "def456",
        "POSTMERGE_APPLICABLE": "false",
    })

    from aria_esi.prompt_review.matcher import select_prompts
    selected = select_prompts(
        config_path=_CONFIG_PATH,
        event="push",
        changed_files=["src/core/config.py"],
        postmerge_applicable=False,
    )

    with patch.object(runtime, '_git_changed_files', return_value=(["src/core/config.py"], "normal", None, None)):
        with patch.object(runtime, 'select_prompts', return_value=selected):
            monkeypatch.chdir(tmp_path)
            result = runtime.main()

    assert result == 0
    combined = json.loads((tmp_path / "artifacts/prompt-results/combined.json").read_text())
    postmerge = [p for p in combined["prompts"] if p["prompt_path"] == "dev/postmerge_regression_audit.md"]
    assert not postmerge or all(p.get("status") == "skipped_not_applicable" for p in postmerge)


def test_workflow_dispatch_without_shas_gate_only_no_fallback(monkeypatch, tmp_path):
    """#22: workflow_dispatch without SHAs runs gate-only mode."""
    runtime = _import_runtime()
    _setup_env(monkeypatch, {"PROMPT_EVENT": "workflow_dispatch"})

    monkeypatch.chdir(tmp_path)
    result = runtime.main()

    assert result == 0
    combined = json.loads((tmp_path / "artifacts/prompt-results/combined.json").read_text())
    assert combined["matcher"]["mode"] == "not_applicable"
    # Only gate prompts should be present
    for prompt in combined["prompts"]:
        assert prompt["tier"] == "gate"


def test_workflow_dispatch_with_shas_runs_normal_matcher_and_fallback(monkeypatch, tmp_path):
    """#23: workflow_dispatch with SHAs runs normal matcher."""
    runtime = _import_runtime()
    _setup_env(monkeypatch, {
        "PROMPT_EVENT": "workflow_dispatch",
        "PROMPT_BASE_SHA": "abc123",
        "PROMPT_HEAD_SHA": "def456",
    })

    from aria_esi.prompt_review.matcher import select_prompts
    selected = select_prompts(
        config_path=_CONFIG_PATH,
        event="workflow_dispatch",
        changed_files=["src/foo.py"],
    )

    with patch.object(runtime, '_git_changed_files', return_value=(["src/foo.py"], "normal", None, None)):
        with patch.object(runtime, 'select_prompts', return_value=selected):
            monkeypatch.chdir(tmp_path)
            result = runtime.main()

    assert result == 0
    combined = json.loads((tmp_path / "artifacts/prompt-results/combined.json").read_text())
    assert combined["matcher"]["mode"] == "normal"


def test_pull_request_missing_base_or_head_sha_fails_closed(monkeypatch, tmp_path):
    """#24: Pull request with missing SHAs fails closed."""
    runtime = _import_runtime()
    _setup_env(monkeypatch, {
        "PROMPT_EVENT": "pull_request",
        "PROMPT_BASE_SHA": "abc123",
        "PROMPT_HEAD_SHA": "def456",
    })

    with patch.object(runtime, '_git_changed_files', return_value=([], "fail_closed", "missing_or_unfetchable_shas", None)):
        monkeypatch.chdir(tmp_path)
        result = runtime.main()

    assert result == 0
    combined = json.loads((tmp_path / "artifacts/prompt-results/combined.json").read_text())
    assert combined["matcher"]["mode"] == "fail_closed"
    assert combined["gate_decision"] == "fail"


def test_bootstrap_missing_prompt_emission_cardinality(monkeypatch, tmp_path):
    """#43: Each selected prompt emits exactly one entry in the output."""
    runtime = _import_runtime()
    _setup_env(monkeypatch, {
        "PROMPT_EVENT": "pull_request",
        "PROMPT_BASE_SHA": "abc123",
        "PROMPT_HEAD_SHA": "def456",
    })

    from aria_esi.prompt_review.matcher import select_prompts
    selected = select_prompts(
        config_path=_CONFIG_PATH,
        event="pull_request",
        changed_files=["src/aria_esi/mcp/server.py"],
    )

    with patch.object(runtime, '_git_changed_files', return_value=(["src/aria_esi/mcp/server.py"], "normal", None, None)):
        with patch.object(runtime, 'select_prompts', return_value=selected):
            monkeypatch.chdir(tmp_path)
            runtime.main()

    combined = json.loads((tmp_path / "artifacts/prompt-results/combined.json").read_text())
    instance_ids = [p["prompt_instance_id"] for p in combined["prompts"]]
    # Each instance ID should be unique
    assert len(instance_ids) == len(set(instance_ids))


def test_windows_proposal_path_normalization_accepts_backslashes():
    """#44: Windows-style backslash paths are normalized to forward slashes."""
    runtime = _import_runtime()
    normalized = runtime._normalize_proposal_path("dev\\proposals\\TEST.md")
    assert "\\" not in normalized
    assert normalized == "dev/proposals/TEST.md"


def test_mixed_valid_invalid_proposal_fanout_partial_behavior():
    """#46: Invalid proposal paths produce not-applicable entries."""
    runtime = _import_runtime()

    valid, error = runtime._validate_manual_proposal_path("dev/proposals/VALID.md")
    assert valid == "dev/proposals/VALID.md"
    assert error is None

    invalid, error = runtime._validate_manual_proposal_path("../../etc/passwd")
    assert invalid is None
    assert error == "invalid_proposal_path"


def test_proposal_path_validation_rejects_archive_symlink_traversal_non_md():
    """#33: Archive paths, traversal, and non-md are rejected."""
    runtime = _import_runtime()

    # Archive path
    _, error = runtime._validate_manual_proposal_path("dev/proposals/archive/OLD.md")
    assert error == "invalid_proposal_path"

    # Path traversal
    _, error = runtime._validate_manual_proposal_path("dev/proposals/../../secrets.md")
    assert error == "invalid_proposal_path"

    # Non-md extension
    _, error = runtime._validate_manual_proposal_path("dev/proposals/evil.py")
    assert error == "invalid_proposal_path"

    # Absolute path
    _, error = runtime._validate_manual_proposal_path("/etc/passwd")
    assert error == "invalid_proposal_path"
