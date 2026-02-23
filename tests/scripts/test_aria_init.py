from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _stage_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    shutil.copy2(REPO_ROOT / "aria-init", workspace / "aria-init")
    (workspace / "aria-init").chmod(0o755)
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


def test_heredoc_targets_exist_in_script() -> None:
    """Verify aria-init generates all expected data files via heredocs."""
    script = (REPO_ROOT / "aria-init").read_text(encoding="utf-8")

    expected_targets = [
        '$DATA_DIR/profile.md',
        '$DATA_DIR/operations.md',
        '$DATA_DIR/missions.md',
        '$DATA_DIR/exploration.md',
        '$DATA_DIR/goals.md',
        '$INDUSTRY_DIR/blueprints.md',
    ]
    for target in expected_targets:
        assert f'cat > "{target}" << EOF' in script or f"cat > \"{target}\" << 'EOF'" in script

    # ships.md uses a quoted heredoc (no variable expansion)
    assert "cat > \"$DATA_DIR/ships.md\" << 'EOF'" in script


def test_persona_context_stub_appended_to_profile(tmp_path: Path) -> None:
    """Verify --test mode appends persona_context stub to profile.md."""
    workspace = _stage_workspace(tmp_path)

    result = _run_init(workspace, ["--test"])
    assert result.returncode == 0, _combined_output(result)

    profile = (workspace / "userdata" / "pilots" / "0_test_capsuleer" / "profile.md").read_text(
        encoding="utf-8"
    )
    assert "## Persona Context" in profile
    assert "persona_context:" in profile
    assert 'rp_level: "off"' in profile
    assert "files: []" in profile
    # Gallente faction maps to aria-mk4
    assert 'persona: "aria-mk4"' in profile
    assert 'branch: "empire"' in profile


def test_ships_md_is_minimal_placeholder(tmp_path: Path) -> None:
    """Verify ships.md is a minimal ESI placeholder without hardcoded ship names."""
    workspace = _stage_workspace(tmp_path)

    result = _run_init(workspace, ["--test"])
    assert result.returncode == 0, _combined_output(result)

    ships = (workspace / "userdata" / "pilots" / "0_test_capsuleer" / "ships.md").read_text(
        encoding="utf-8"
    )
    assert "ESI sync" in ships
    # Should NOT contain specific ship names from the old elaborate scaffolding
    assert "Venture" not in ships
    assert "Miner I" not in ships
    assert "Future Acquisitions" not in ships


def test_missions_md_references_index_instead_of_inline_profiles(tmp_path: Path) -> None:
    """Verify missions.md points to reference/pve-intel/INDEX.md instead of inline damage profiles."""
    workspace = _stage_workspace(tmp_path)

    result = _run_init(workspace, ["--test"])
    assert result.returncode == 0, _combined_output(result)

    missions = (workspace / "userdata" / "pilots" / "0_test_capsuleer" / "missions.md").read_text(
        encoding="utf-8"
    )
    assert "reference/pve-intel/INDEX.md" in missions
    # Should NOT contain inline faction damage profiles
    assert "Damage Dealt:" not in missions
    assert "Damage to Deal:" not in missions


def test_operations_md_references_profile_and_ships(tmp_path: Path) -> None:
    """Verify operations.md doesn't duplicate faction alignment or ship roster data."""
    workspace = _stage_workspace(tmp_path)

    result = _run_init(workspace, ["--test"])
    assert result.returncode == 0, _combined_output(result)

    ops = (workspace / "userdata" / "pilots" / "0_test_capsuleer" / "operations.md").read_text(
        encoding="utf-8"
    )
    # Faction alignment should reference profile.md
    assert "See `profile.md` for faction alignment" in ops
    # Ship roster should reference ships.md
    assert "See `ships.md`" in ops
    # Should NOT duplicate faction data
    assert "Primary Alignment:" not in ops
    assert "Hostile Factions:" not in ops


def test_all_canonical_files_created_in_test_mode(tmp_path: Path) -> None:
    """Verify --test creates exactly the expected set of pilot files."""
    workspace = _stage_workspace(tmp_path)

    result = _run_init(workspace, ["--test"])
    assert result.returncode == 0, _combined_output(result)

    pilot_dir = workspace / "userdata" / "pilots" / "0_test_capsuleer"
    expected_files = [
        "profile.md",
        "operations.md",
        "ships.md",
        "missions.md",
        "exploration.md",
        "goals.md",
        "industry/blueprints.md",
    ]
    for rel in expected_files:
        assert (pilot_dir / rel).exists(), f"Missing: {rel}"

    # Negative: no blueprints.md at pilot root (only in industry/)
    assert not (pilot_dir / "blueprints.md").exists(), "Orphan blueprints.md at pilot root"


def test_persona_context_stub_is_valid_yaml(tmp_path: Path) -> None:
    """Verify the persona_context stub injected into profile.md is parseable YAML."""
    workspace = _stage_workspace(tmp_path)

    result = _run_init(workspace, ["--test"])
    assert result.returncode == 0, _combined_output(result)

    profile = (workspace / "userdata" / "pilots" / "0_test_capsuleer" / "profile.md").read_text(
        encoding="utf-8"
    )
    # Extract YAML block from fenced code block
    match = re.search(r"```yaml\n(.*?)```", profile, re.DOTALL)
    assert match, "No YAML code block found in profile.md"

    parsed = yaml.safe_load(match.group(1))
    ctx = parsed["persona_context"]
    assert ctx["branch"] == "empire"
    assert ctx["persona"] == "aria-mk4"
    assert ctx["rp_level"] == "off"
    assert ctx["files"] == []
    assert ctx["fallback"] is None
    assert "skill-overlays" in ctx["skill_overlay_path"]


def test_persona_stub_mapping_matches_python_faction_map() -> None:
    """Verify bash inject_persona_context_stub covers all empire factions
    and maps consistently with Python FACTION_PERSONA_MAP."""
    # Load the Python-side mapping
    from aria_esi.commands.persona import FACTION_PERSONA_MAP

    script = (REPO_ROOT / "aria-init").read_text(encoding="utf-8")

    # Extract all faction→persona mappings from the bash case statement
    # Pattern: FACTION)  persona="name"; branch="branch" ;;
    bash_mappings: dict[str, dict[str, str]] = {}
    for match in re.finditer(
        r'(\w+)\)\s+persona="([^"]+)";\s+branch="([^"]+)"',
        script,
    ):
        faction, persona, branch = match.groups()
        bash_mappings[faction.lower()] = {"persona": persona, "branch": branch}

    # All four empire factions must be present in bash
    for faction in ("gallente", "caldari", "minmatar", "amarr"):
        assert faction in bash_mappings, f"Missing bash mapping for {faction}"
        py = FACTION_PERSONA_MAP[faction]
        assert bash_mappings[faction]["persona"] == py["persona"], (
            f"{faction}: bash persona={bash_mappings[faction]['persona']} != python persona={py['persona']}"
        )
        assert bash_mappings[faction]["branch"] == py["branch"], (
            f"{faction}: bash branch={bash_mappings[faction]['branch']} != python branch={py['branch']}"
        )


def test_no_templates_directory_required(tmp_path: Path) -> None:
    """Verify aria-init works without a templates/ directory.

    This is the primary regression test for Phase 1c: the templates/
    prerequisite check was removed and the directory deleted.
    """
    workspace = _stage_workspace(tmp_path)
    # Explicitly ensure no templates directory exists
    assert not (workspace / "templates").exists()

    result = _run_init(workspace, ["--test"])
    output = _combined_output(result)

    assert result.returncode == 0, output
    # Must not complain about missing templates
    assert "Templates directory not found" not in output
    assert "Missing template" not in output


def test_missions_md_standings_not_duplicated(tmp_path: Path) -> None:
    """Verify missions.md doesn't contain inline standing tables (deduplication)."""
    workspace = _stage_workspace(tmp_path)

    result = _run_init(workspace, ["--test"])
    assert result.returncode == 0, _combined_output(result)

    missions = (workspace / "userdata" / "pilots" / "0_test_capsuleer" / "missions.md").read_text(
        encoding="utf-8"
    )
    # Standing Progress should be a pointer, not inline tables
    assert "See `profile.md`" in missions
    # Should NOT contain per-corporation standing tables
    assert "| Date | Standing | Change | Source |" not in missions
