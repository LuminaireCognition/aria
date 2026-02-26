"""Cross-implementation slug tests and runtime detection tests.

Verifies bash slugify_name() and Python pilot_slug() produce identical
output for shared test vectors. Also tests aria-init runtime detection
and credential scanning.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Load Python slug implementation
OAUTH_SCRIPT_PATH = REPO_ROOT / ".claude" / "scripts" / "aria-oauth-setup.py"
spec = importlib.util.spec_from_file_location("aria_oauth_setup", OAUTH_SCRIPT_PATH)
oauth_setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oauth_setup)


def _bash_slugify(name: str) -> str:
    """Invoke bash slugify_name() extracted from the actual aria-init script."""
    script_text = (REPO_ROOT / "aria-init").read_text(encoding="utf-8")
    match = re.search(r"(slugify_name\(\) \{.*?\n\})", script_text, re.DOTALL)
    assert match, "slugify_name() not found in aria-init"
    func_body = match.group(1)
    result = subprocess.run(
        ["bash", "-c", f"{func_body}\nslugify_name \"$1\"", "_", name],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"bash slugify_name failed: {result.stderr}"
    return result.stdout


# ── Slug cross-implementation vectors ────────────────────────────

SLUG_VECTORS = [
    ("Simple Name", "simple_name"),
    ("UPPER CASE", "upper_case"),
    ("  spaces  ", "__spaces__"),
    ("test-pilot_v2", "testpilot_v2"),
    ("12345", "12345"),
    ("a" * 100, "a" * 32),
    ("", "pilot"),
    ("!!!@@@###", "pilot"),
    ("hello world 123", "hello_world_123"),
    ("Caf\u00e9 Pilot\u00e9", "caf_pilot"),        # accented Latin (é stripped)
    ("\u00d1o\u00f1o", "oo"),                        # Ñoño - tilde stripped
    ("\u65e5\u672c\u8a9e", "pilot"),                 # Japanese CJK - all stripped → fallback
    ("Zo\u00eb-X", "zox"),                           # diaeresis + hyphen stripped
]


@pytest.mark.parametrize(
    "input_name,expected",
    SLUG_VECTORS,
    ids=[v[0][:20] or "(empty)" for v in SLUG_VECTORS],
)
def test_slug_python_matches_expected(input_name: str, expected: str) -> None:
    assert oauth_setup.pilot_slug(input_name) == expected


@pytest.mark.parametrize(
    "input_name,expected",
    SLUG_VECTORS,
    ids=[v[0][:20] or "(empty)" for v in SLUG_VECTORS],
)
def test_slug_bash_matches_expected(input_name: str, expected: str) -> None:
    assert _bash_slugify(input_name) == expected


@pytest.mark.parametrize(
    "input_name",
    [v[0] for v in SLUG_VECTORS],
    ids=[v[0][:20] or "(empty)" for v in SLUG_VECTORS],
)
def test_slug_bash_matches_python(input_name: str) -> None:
    """Bash and Python slug implementations produce identical output."""
    python_slug = oauth_setup.pilot_slug(input_name)
    bash_slug = _bash_slugify(input_name)
    assert bash_slug == python_slug, (
        f"Divergence for input {input_name!r}: bash={bash_slug!r}, python={python_slug!r}"
    )


# ── Workspace helpers ────────────────────────────────────────────


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


# ── Runtime detection ────────────────────────────────────────────


def test_runtime_detection_prints_classification(tmp_path: Path) -> None:
    """aria-init --test prints a runtime classification line."""
    workspace = _stage_workspace(tmp_path)
    (workspace / "userdata" / "credentials" / "12345.json").write_text("{}", encoding="utf-8")

    result = _run_init(workspace, ["--test"])
    output = _combined_output(result)

    classifications = ["Linux", "WSL2", "macOS", "container"]
    assert any(
        f"Runtime: {c}" in output for c in classifications
    ), f"No runtime classification found in output: {output[:500]}"


def test_help_flag_works(tmp_path: Path) -> None:
    """--help works and prints usage."""
    workspace = _stage_workspace(tmp_path)
    result = _run_init(workspace, ["--help"])
    assert result.returncode == 0
    assert "usage" in result.stdout.lower() or "Usage" in result.stdout


def test_version_flag_works(tmp_path: Path) -> None:
    """--version outputs a version string."""
    workspace = _stage_workspace(tmp_path)
    result = _run_init(workspace, ["--version"])
    assert result.returncode == 0


# ── Credential scanning ─────────────────────────────────────────


def test_non_numeric_credential_files_ignored_in_init(tmp_path: Path) -> None:
    """aria-init ignores .gitkeep and non-numeric .json during credential scan."""
    workspace = _stage_workspace(tmp_path)
    creds = workspace / "userdata" / "credentials"
    (creds / ".gitkeep").write_text("", encoding="utf-8")
    (creds / "backup.json").write_text("{}", encoding="utf-8")
    (creds / "12345.json").write_text("{}", encoding="utf-8")

    result = _run_init(workspace, ["--test"])
    output = _combined_output(result)

    assert result.returncode == 0, output
    pilot_dirs = [
        d for d in (workspace / "userdata" / "pilots").iterdir()
        if d.is_dir() and d.name.startswith("12345_")
    ]
    assert len(pilot_dirs) == 1, f"Expected exactly one 12345_* dir, got: {pilot_dirs}"


def test_multiple_numeric_credentials_fails_in_init(tmp_path: Path) -> None:
    """Multiple numeric credential files → aria-init fails with non-zero exit.

    Note: The error message is captured by $() subshell, so it may not
    appear in stdout/stderr. The non-zero exit code is the observable contract.
    """
    workspace = _stage_workspace(tmp_path)
    creds = workspace / "userdata" / "credentials"
    (creds / "11111.json").write_text("{}", encoding="utf-8")
    (creds / "22222.json").write_text("{}", encoding="utf-8")

    result = _run_init(workspace, ["--test"])
    assert result.returncode != 0


def test_known_id_directory_invariant_reuses_existing(tmp_path: Path) -> None:
    """If {id}_* directory already exists, aria-init reuses it."""
    workspace = _stage_workspace(tmp_path)
    (workspace / "userdata" / "credentials" / "12345.json").write_text("{}", encoding="utf-8")
    (workspace / "userdata" / "pilots" / "12345_old_slug").mkdir()

    result = _run_init(workspace, ["--test"])
    output = _combined_output(result)

    assert result.returncode == 0, output
    assert (workspace / "userdata" / "pilots" / "12345_old_slug").is_dir()


def test_known_id_directory_multiple_fails(tmp_path: Path) -> None:
    """Multiple {id}_* directories → explicit error."""
    workspace = _stage_workspace(tmp_path)
    (workspace / "userdata" / "credentials" / "12345.json").write_text("{}", encoding="utf-8")
    (workspace / "userdata" / "pilots" / "12345_alpha").mkdir()
    (workspace / "userdata" / "pilots" / "12345_beta").mkdir()

    result = _run_init(workspace, ["--test"])
    output = _combined_output(result)

    assert result.returncode != 0
    assert "12345_alpha" in output or "12345_beta" in output


def test_no_old_template_references() -> None:
    """No references to old template filenames in active content."""
    old_names = [
        "pilot_profile.template.md",
        "operational_profile.template.md",
        "ship_status.template.md",
        "mission_log.template.md",
        "exploration_catalog.template.md",
        "blueprint_library.template.md",
    ]
    script = (REPO_ROOT / "aria-init").read_text(encoding="utf-8")
    for name in old_names:
        assert name not in script, f"Old template name {name!r} found in aria-init"
