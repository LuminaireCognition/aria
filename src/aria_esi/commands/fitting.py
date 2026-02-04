"""
ARIA ESI Fitting Commands

Commands for managing EOS fitting calculation data.
"""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..core import get_utc_timestamp
from ..core.data_integrity import (
    get_eos_repository,
    get_pinned_eos_commit,
    is_break_glass_enabled,
)

# =============================================================================
# Constants
# =============================================================================

PYFA_REPO = "https://github.com/pyfa-org/Pyfa.git"

# Files to merge from each directory
FSD_BUILT_FILES = [
    "types",
    "groups",
    "categories",
    "dogmaattributes",
    "dogmaeffects",
    "typedogma",
    "requiredskillsfortypes",
]

FSD_LITE_FILES = [
    "dbuffcollections",
    "clonegrades",
]

PHOBOS_FILES = [
    "metadata",
]


# =============================================================================
# Helper Functions
# =============================================================================


def merge_numbered_json_files(source_dir: Path, target_dir: Path, filename_base: str) -> int:
    """
    Merge files like 'types.0.json', 'types.1.json' into 'types.json'.

    Returns the number of records merged.
    """
    merged_data: dict | list = {}
    file_index = 0

    while True:
        source_file = source_dir / f"{filename_base}.{file_index}.json"
        if not source_file.exists():
            break

        print(f"  Loading {source_file.name}...")
        with open(source_file, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            if isinstance(merged_data, dict):
                merged_data.update(data)
            else:
                merged_data = data
        elif isinstance(data, list):
            merged_data = data

        file_index += 1

    if file_index == 0:
        print(f"  WARNING: No files found for {filename_base}")
        return 0

    target_file = target_dir / f"{filename_base}.json"
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(merged_data, f)

    record_count = len(merged_data) if isinstance(merged_data, dict) else len(merged_data)
    print(f"  Merged {file_index} files -> {target_file.name} ({record_count:,} records)")
    return record_count


def prepare_eos_data(pyfa_staticdata: Path, output_dir: Path) -> dict:
    """Prepare EOS-compatible data from Pyfa's staticdata directory."""
    stats = {"files": 0, "records": 0}

    fsd_built_out = output_dir / "fsd_built"
    fsd_lite_out = output_dir / "fsd_lite"
    phobos_out = output_dir / "phobos"

    for d in [fsd_built_out, fsd_lite_out, phobos_out]:
        d.mkdir(parents=True, exist_ok=True)

    print("\n=== Merging fsd_built files ===")
    fsd_built_src = pyfa_staticdata / "fsd_built"
    for filename in FSD_BUILT_FILES:
        count = merge_numbered_json_files(fsd_built_src, fsd_built_out, filename)
        if count > 0:
            stats["files"] += 1
            stats["records"] += count

    print("\n=== Merging fsd_lite files ===")
    fsd_lite_src = pyfa_staticdata / "fsd_lite"
    for filename in FSD_LITE_FILES:
        count = merge_numbered_json_files(fsd_lite_src, fsd_lite_out, filename)
        if count > 0:
            stats["files"] += 1
            stats["records"] += count

    print("\n=== Creating placeholder files ===")
    fighter_file = fsd_lite_out / "fighterabilitiesbytype.json"
    if not fighter_file.exists():
        print(f"  Creating empty placeholder: {fighter_file.name}")
        with open(fighter_file, "w", encoding="utf-8") as f:
            json.dump({}, f)
        stats["files"] += 1

    print("\n=== Merging phobos files ===")
    phobos_src = pyfa_staticdata / "phobos"
    for filename in PHOBOS_FILES:
        merge_numbered_json_files(phobos_src, phobos_out, filename)
        stats["files"] += 1

    return stats


def download_pyfa_staticdata(temp_dir: Path, break_glass: bool = False) -> tuple[Path, str | None]:
    """
    Download Pyfa staticdata using sparse checkout with optional commit pinning.

    Args:
        temp_dir: Temporary directory for cloning
        break_glass: If True, skip commit pinning (use HEAD)

    Returns:
        Tuple of (staticdata_path, commit_hash)
    """
    print("=== Downloading Pyfa staticdata ===")
    print("  This may take a moment...")

    repo_dir = temp_dir / "pyfa"
    repo_url = get_eos_repository()
    pinned_commit = get_pinned_eos_commit()

    # Determine if we should use pinning
    effective_break_glass = break_glass or is_break_glass_enabled()

    if pinned_commit and not effective_break_glass:
        print(f"  Using pinned commit: {pinned_commit[:12]}")
        # Clone without depth to allow checkout of specific commit
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--sparse", repo_url, str(repo_dir)],
            check=True,
            capture_output=True,
        )
        # Checkout the specific commit
        subprocess.run(
            ["git", "-C", str(repo_dir), "checkout", pinned_commit],
            check=True,
            capture_output=True,
        )
    else:
        if pinned_commit and effective_break_glass:
            print("  WARNING: Break-glass mode, using HEAD instead of pinned commit")
        elif not pinned_commit:
            print("  No pinned commit configured, using HEAD")
        # Standard shallow clone
        subprocess.run(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--sparse",
                "--depth=1",
                repo_url,
                str(repo_dir),
            ],
            check=True,
            capture_output=True,
        )

    subprocess.run(
        ["git", "-C", str(repo_dir), "sparse-checkout", "set", "staticdata"],
        check=True,
        capture_output=True,
    )

    # Get actual commit hash
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        actual_commit = result.stdout.strip()
    except subprocess.CalledProcessError:
        actual_commit = None

    staticdata_path = repo_dir / "staticdata"
    if not staticdata_path.exists():
        raise RuntimeError("Failed to download Pyfa staticdata")

    print(f"  Downloaded to: {staticdata_path}")
    if actual_commit:
        print(f"  Commit: {actual_commit[:12]}")

    return staticdata_path, actual_commit


# =============================================================================
# EOS Seed Command
# =============================================================================


def cmd_eos_seed(args: argparse.Namespace) -> dict:
    """
    Download and prepare EOS fitting data from Pyfa.

    Downloads the EVE static data from Pyfa's GitHub repository and
    prepares it in the format required by the EOS fitting engine.
    """
    from aria_esi.fitting import get_eos_data_manager

    query_ts = get_utc_timestamp()
    force = getattr(args, "force", False)
    check_only = getattr(args, "check", False)
    break_glass = getattr(args, "break_glass_latest", False)

    data_manager = get_eos_data_manager()
    output_dir = data_manager.data_path

    print("=" * 60)
    print("EOS DATA PREPARATION")
    print("=" * 60)

    if break_glass:
        print("WARNING: Break-glass mode enabled, ignoring commit pinning")

    # Check-only mode
    if check_only:
        status = data_manager.validate()
        return {
            "command": "eos-seed",
            "mode": "check",
            "is_valid": status.is_valid,
            "data_path": str(status.data_path),
            "version": status.version,
            "missing_files": status.missing_files,
            "total_records": status.total_records,
            "query_timestamp": query_ts,
        }

    # Check if data already exists
    if output_dir.exists() and not force:
        status = data_manager.validate()
        if status.is_valid:
            print(f"\nEOS data already exists at: {output_dir}")
            print(f"Version: {status.version or 'unknown'}")
            print("\nUse --force to re-download")
            return {
                "command": "eos-seed",
                "status": "already_exists",
                "data_path": str(output_dir),
                "version": status.version,
                "hint": "Use --force to re-download",
                "query_timestamp": query_ts,
            }

    print(f"Output directory: {output_dir}")

    # Download and prepare data
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            staticdata_path, source_commit = download_pyfa_staticdata(
                Path(temp_dir), break_glass=break_glass
            )

            # Clean output directory if it exists
            if output_dir.exists():
                print(f"\nRemoving existing data at: {output_dir}")
                shutil.rmtree(output_dir)

            # Prepare EOS data
            stats = prepare_eos_data(staticdata_path, output_dir)

            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            print(f"Files created: {stats['files']}")
            print(f"Total records: {stats['records']:,}")
            print(f"Output directory: {output_dir}")
            if source_commit:
                print(f"Source commit: {source_commit}")

            # Invalidate cache and verify
            data_manager.invalidate_cache()
            final_status = data_manager.validate()

            if final_status.is_valid:
                print(f"\n EOS data prepared successfully (version: {final_status.version})")
                response = {
                    "command": "eos-seed",
                    "status": "success",
                    "data_path": str(output_dir),
                    "version": final_status.version,
                    "files_created": stats["files"],
                    "total_records": stats["records"],
                    "query_timestamp": query_ts,
                }
                if source_commit:
                    response["source_commit"] = source_commit
                return response
            else:
                print(f"\n Validation failed: {final_status.error_message}")
                return {
                    "command": "eos-seed",
                    "status": "validation_failed",
                    "error": final_status.error_message,
                    "missing_files": final_status.missing_files,
                    "query_timestamp": query_ts,
                }

        except subprocess.CalledProcessError:
            error_msg = (
                "Git operation failed. Make sure git is installed and you have internet access"
            )
            print(f"\n✗ {error_msg}")
            return {
                "error": "git_error",
                "message": error_msg,
                "query_timestamp": query_ts,
            }
        except Exception as e:
            print(f"\n✗ Error: {e}")
            return {
                "error": "seed_error",
                "message": str(e),
                "query_timestamp": query_ts,
            }


# =============================================================================
# EOS Status Command
# =============================================================================


def cmd_eos_status(args: argparse.Namespace) -> dict:
    """
    Check EOS fitting data status.

    Shows the current status of the EOS data files including version,
    available files, and any missing required files.
    """
    from aria_esi.fitting import get_eos_data_manager

    query_ts = get_utc_timestamp()

    data_manager = get_eos_data_manager()
    status = data_manager.validate()

    result = status.to_dict()
    result["command"] = "eos-status"
    result["query_timestamp"] = query_ts

    # Print human-readable output
    print("=" * 60)
    print("EOS DATA STATUS")
    print("=" * 60)
    print(f"Data path: {status.data_path}")
    print(f"Status: {'Valid' if status.is_valid else 'Invalid'}")
    print(f"Version: {status.version or 'unknown'}")
    print(f"Total records: {status.total_records:,}")

    if status.missing_files:
        print(f"\nMissing files: {status.missing_files}")
        print("\nRun 'aria-esi eos-seed' to download data")

    if status.is_valid:
        print("\nFiles:")
        for category, files in [
            ("fsd_built", status.fsd_built_files),
            ("fsd_lite", status.fsd_lite_files),
            ("phobos", status.phobos_files),
        ]:
            if files:
                print(f"  {category}/: {len(files)} files")

    return result


# =============================================================================
# Parser Registration
# =============================================================================


def register_parsers(subparsers) -> None:
    """Register fitting command parsers."""

    # eos-seed command
    seed_parser = subparsers.add_parser(
        "eos-seed",
        help="Download and prepare EOS fitting data",
        description="Download EVE static data from Pyfa and prepare for EOS fitting calculations",
    )
    seed_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force re-download even if data exists",
    )
    seed_parser.add_argument(
        "--check",
        action="store_true",
        help="Check current data status without downloading",
    )
    seed_parser.add_argument(
        "--break-glass-latest",
        action="store_true",
        dest="break_glass_latest",
        help="Skip commit pinning (use HEAD)",
    )
    seed_parser.set_defaults(func=cmd_eos_seed)

    # eos-status command
    status_parser = subparsers.add_parser(
        "eos-status",
        help="Check EOS fitting data status",
        description="Show status of EOS fitting data files",
    )
    status_parser.set_defaults(func=cmd_eos_status)
