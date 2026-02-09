from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _stage_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    shutil.copy2(REPO_ROOT / "aria-init", workspace / "aria-init")
    (workspace / "aria-init").chmod(0o755)
    shutil.copytree(REPO_ROOT / "templates", workspace / "templates")
    (workspace / "userdata" / "pilots").mkdir(parents=True)
    (workspace / "userdata" / "credentials").mkdir(parents=True)
    return workspace


def _run_init(
    workspace: Path,
    args: list[str],
    *,
    input_text: str = "",
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    test_bin = workspace / ".test-bin"
    test_bin.mkdir(exist_ok=True)
    (test_bin / "clear").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (test_bin / "clear").chmod(0o755)

    env = os.environ.copy()
    env.setdefault("TERM", "xterm")
    env["PATH"] = f"{test_bin}:{env['PATH']}"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(workspace / "aria-init"), *args],
        cwd=workspace,
        input=input_text,
        text=True,
        capture_output=True,
        env=env,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _interactive_answers() -> str:
    # ready, name, faction, corp, home, activity, self-sufficient, confirm, then "n"
    return "y\nTest Pilot\n1\n\n\n4\nn\ny\nn\n"


def test_multi_registry_without_selector_fails(tmp_path: Path) -> None:
    workspace = _stage_workspace(tmp_path)
    registry = {
        "schema_version": "1.0",
        "pilots": [
            {"character_id": "1001", "directory": "1001_alpha"},
            {"character_id": "1002", "directory": "1002_bravo"},
        ],
    }
    (workspace / "userdata" / "pilots" / "_registry.json").write_text(json.dumps(registry), encoding="utf-8")

    result = _run_init(workspace, ["--test"])
    output = _combined_output(result)

    assert result.returncode != 0
    assert "Multiple pilots found in userdata/pilots/_registry.json with no selector" in output
    assert "Registered pilots:" in output
    assert "1001" in output
    assert "1002" in output


def test_selector_not_in_registry_uses_selected_id_directly(tmp_path: Path) -> None:
    workspace = _stage_workspace(tmp_path)
    registry = {
        "schema_version": "1.0",
        "pilots": [{"character_id": "1001", "directory": "1001_alpha"}],
    }
    (workspace / "userdata" / "pilots" / "_registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (workspace / "userdata" / "credentials" / "2111.json").write_text("{}", encoding="utf-8")

    result = _run_init(
        workspace,
        ["--test"],
        extra_env={"ARIA_PILOT": "9999"},
    )
    output = _combined_output(result)

    assert result.returncode == 0, output
    assert "Selected pilot ID '9999' was not found in userdata/pilots/_registry.json." in output
    assert "Using selected pilot ID '9999' directly." in output
    assert (workspace / "userdata" / "pilots" / "9999_test_capsuleer" / "profile.md").exists()
    assert not (workspace / "userdata" / "pilots" / "2111_test_capsuleer" / "profile.md").exists()


def test_selector_with_missing_registry_uses_selected_id_directly(tmp_path: Path) -> None:
    workspace = _stage_workspace(tmp_path)
    (workspace / "userdata" / "credentials" / "31337.json").write_text("{}", encoding="utf-8")

    result = _run_init(
        workspace,
        ["--test"],
        extra_env={"ARIA_PILOT": "9999"},
    )
    output = _combined_output(result)

    assert result.returncode == 0, output
    assert "cannot be resolved because userdata/pilots/_registry.json is missing." in output
    assert "Using selected pilot ID '9999' directly." in output
    assert (workspace / "userdata" / "pilots" / "9999_test_capsuleer" / "profile.md").exists()
    assert not (workspace / "userdata" / "pilots" / "31337_test_capsuleer" / "profile.md").exists()


def test_selector_with_corrupt_registry_uses_selected_id_directly(tmp_path: Path) -> None:
    workspace = _stage_workspace(tmp_path)
    (workspace / "userdata" / "pilots" / "_registry.json").write_text("{", encoding="utf-8")
    (workspace / "userdata" / "credentials" / "12345.json").write_text("{}", encoding="utf-8")

    result = _run_init(
        workspace,
        ["--test"],
        extra_env={"ARIA_PILOT": "9999"},
    )
    output = _combined_output(result)

    assert result.returncode == 0, output
    assert "Invalid JSON in userdata/pilots/_registry.json." in output
    assert "Using selected pilot ID '9999' directly." in output
    assert (workspace / "userdata" / "pilots" / "9999_test_capsuleer" / "profile.md").exists()
    assert not (workspace / "userdata" / "pilots" / "12345_test_capsuleer" / "profile.md").exists()


def test_single_registry_entry_auto_selected_in_test_mode(tmp_path: Path) -> None:
    workspace = _stage_workspace(tmp_path)
    registry = {
        "schema_version": "1.0",
        "pilots": [{"character_id": "2111", "directory": "2111_single_pilot"}],
    }
    (workspace / "userdata" / "pilots" / "_registry.json").write_text(json.dumps(registry), encoding="utf-8")

    result = _run_init(workspace, ["--test"])
    output = _combined_output(result)

    assert result.returncode == 0, output
    assert (workspace / "userdata" / "pilots" / "2111_single_pilot" / "profile.md").exists()


def test_corrupt_recovery_aborts_by_default(tmp_path: Path) -> None:
    workspace = _stage_workspace(tmp_path)
    (workspace / "userdata" / "pilots" / "_registry.json").write_text("{", encoding="utf-8")
    (workspace / "userdata" / "config.json").write_text("{", encoding="utf-8")
    (workspace / "userdata" / "credentials" / "12345.json").write_text("{}", encoding="utf-8")

    result = _run_init(workspace, [], input_text=_interactive_answers())
    output = _combined_output(result)

    assert result.returncode != 0
    assert "Corrupt JSON files were detected during runtime-state update." in output
    assert "Aborted after corruption recovery." in output
    assert (workspace / "userdata" / "pilots" / "_registry.json").read_text(encoding="utf-8") == "{"
    assert (workspace / "userdata" / "config.json").read_text(encoding="utf-8") == "{"
    assert list((workspace / "userdata" / "pilots").glob("_registry.json.corrupt.*"))
    assert list((workspace / "userdata").glob("config.json.corrupt.*"))


def test_corrupt_recovery_force_skips_prompt_and_warns_on_orphans(tmp_path: Path) -> None:
    workspace = _stage_workspace(tmp_path)
    (workspace / "userdata" / "pilots" / "_registry.json").write_text("{", encoding="utf-8")
    (workspace / "userdata" / "credentials" / "12345.json").write_text("{}", encoding="utf-8")
    (workspace / "userdata" / "pilots" / "99999_old_data").mkdir(parents=True)

    result = _run_init(workspace, ["--force"], input_text=_interactive_answers())
    output = _combined_output(result)

    assert result.returncode == 0, output
    assert "--force set; skipping recovery confirmation." in output
    assert "Registry recovered to defaults; found pilot directories not referenced" in output
    assert "99999_old_data" in output

    registry_path = workspace / "userdata" / "pilots" / "_registry.json"
    config_path = workspace / "userdata" / "config.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert any(p.get("character_id") == "12345" for p in registry.get("pilots", []))
    assert config.get("active_pilot") == "12345"
    assert list((workspace / "userdata" / "pilots").glob("_registry.json.corrupt.*"))


def test_corrupt_config_with_healthy_registry_lists_registered_pilots(tmp_path: Path) -> None:
    workspace = _stage_workspace(tmp_path)
    registry = {
        "schema_version": "1.0",
        "pilots": [{"character_id": "2111", "directory": "2111_single_pilot"}],
    }
    (workspace / "userdata" / "pilots" / "_registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (workspace / "userdata" / "config.json").write_text("{", encoding="utf-8")

    result = _run_init(workspace, [], input_text=_interactive_answers())
    output = _combined_output(result)

    assert result.returncode != 0
    assert "Corrupt JSON files were detected during runtime-state update." in output
    assert "Registered pilots:" in output
    assert "2111" in output
    assert "Aborted after corruption recovery." in output


def test_json_contract_supports_jq_or_python_fallback() -> None:
    script = (REPO_ROOT / "aria-init").read_text(encoding="utf-8")
    assert "json_merge_registry()" in script
    assert "json_merge_config()" in script
    assert "jq" in script
    assert "uv run python -c" in script


def test_missing_jq_is_non_fatal_with_python_fallback(tmp_path: Path) -> None:
    workspace = _stage_workspace(tmp_path)
    bash_env = workspace / ".bash_env_no_jq"
    bash_env.write_text(
        "command() {\n"
        "  if [[ \"$1\" == \"-v\" && \"$2\" == \"jq\" ]]; then\n"
        "    return 1\n"
        "  fi\n"
        "  builtin command \"$@\"\n"
        "}\n",
        encoding="utf-8",
    )

    result = _run_init(workspace, ["--test"], extra_env={"BASH_ENV": str(bash_env)})
    output = _combined_output(result)

    assert result.returncode == 0, output
    assert "jq not found on PATH; using uv run python stdlib fallback for JSON operations." in output


def test_template_heredoc_structure_stays_consistent() -> None:
    templates_root = REPO_ROOT / "templates"
    script = (REPO_ROOT / "aria-init").read_text(encoding="utf-8")
    template_paths = sorted(
        str(path.relative_to(templates_root).as_posix())
        for path in templates_root.rglob("*.template.md")
    )
    required_templates = sorted(re.findall(r'"([^"]+\.template\.md)"', script))
    expected_templates = sorted(
        [
            "profile.template.md",
            "operations.template.md",
            "ships.template.md",
            "missions.template.md",
            "exploration.template.md",
            "goals.template.md",
            "industry/blueprints.template.md",
        ]
    )
    assert "industry/blueprints.template.md" in template_paths
    assert required_templates == expected_templates
    assert required_templates == template_paths

    expected_targets = [
        '$DATA_DIR/profile.md',
        '$DATA_DIR/operations.md',
        '$DATA_DIR/ships.md',
        '$DATA_DIR/missions.md',
        '$DATA_DIR/exploration.md',
        '$DATA_DIR/goals.md',
        '$INDUSTRY_DIR/blueprints.md',
    ]
    for target in expected_targets:
        assert f'cat > "{target}" << EOF' in script
