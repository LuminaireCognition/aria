"""
Archetype Migration Module.

Handles migration of archetype files from legacy tier names to new naming scheme:
- low.yaml -> t1.yaml
- medium.yaml -> meta.yaml
- high.yaml -> t2_optimal.yaml
- alpha.yaml -> (merged into t1.yaml with omega_required=false)

Also adds omega_required flag to existing files based on module analysis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from aria_esi.core.logging import get_logger

from .loader import get_hulls_path
from .models import TIER_MIGRATION_MAP

logger = get_logger(__name__)


# =============================================================================
# Migration Result
# =============================================================================


@dataclass
class MigrationAction:
    """A single migration action."""

    action_type: str  # "rename", "update", "delete", "skip"
    source_path: Path
    target_path: Path | None = None
    changes: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result: dict[str, str | list[str]] = {
            "action": self.action_type,
            "source": str(self.source_path),
        }
        if self.target_path:
            result["target"] = str(self.target_path)
        if self.changes:
            result["changes"] = self.changes
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class MigrationResult:
    """Result of migration operation."""

    total_files: int = 0
    migrated: int = 0
    skipped: int = 0
    errors: int = 0
    actions: list[MigrationAction] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_files": self.total_files,
            "migrated": self.migrated,
            "skipped": self.skipped,
            "errors": self.errors,
            "actions": [a.to_dict() for a in self.actions],
        }


# =============================================================================
# T2 Module Detection
# =============================================================================

# Patterns that indicate T2 modules (require omega)
T2_PATTERNS = [
    r" II$",  # Standard T2 suffix
    r" II,",  # T2 with charge
]

# Patterns that indicate meta/compact modules (alpha-friendly)
META_PATTERNS = [
    r"Compact",
    r"Enduring",
    r"Scoped",
    r"Restrained",
    r"Upgraded",
    r"Limited",
    r"Prototype",
]


def _has_t2_modules(eft: str) -> bool:
    """Check if EFT contains T2 modules."""
    for pattern in T2_PATTERNS:
        if re.search(pattern, eft):
            return True
    return False


def _determine_omega_required(data: dict) -> bool:
    """
    Determine if omega is required based on modules.

    Returns True if any T2 modules are present.
    """
    eft = data.get("eft", "")
    skill_tier = data.get("archetype", {}).get("skill_tier", "")

    # Alpha tier is explicitly omega_required=False
    if skill_tier == "alpha":
        return False

    # High tier typically has T2 modules
    if skill_tier == "high":
        return True

    # Check modules for T2
    return _has_t2_modules(eft)


# =============================================================================
# YAML Preservation
# =============================================================================


def _load_yaml_preserve_order(path: Path) -> tuple[dict[str, Any], str]:
    """
    Load YAML file and return both parsed data and raw content.

    Returns:
        Tuple of (parsed_data, raw_content)
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()

    data = yaml.safe_load(content) or {}
    return data, content


def _update_yaml_content(
    content: str,
    old_tier: str,
    new_tier: str,
    add_omega_required: bool | None = None,
) -> str:
    """
    Update YAML content with new tier name and omega_required flag.

    Preserves formatting, comments, and structure.
    """
    # Replace skill_tier value
    content = re.sub(
        rf"skill_tier:\s*{old_tier}",
        f"skill_tier: {new_tier}",
        content,
    )

    # Add omega_required if specified and not already present
    if add_omega_required is not None and "omega_required:" not in content:
        # Insert after skill_tier line
        content = re.sub(
            rf"(skill_tier:\s*{new_tier})",
            f"\\1\n  omega_required: {'true' if add_omega_required else 'false'}",
            content,
        )

    return content


# =============================================================================
# Migration Logic
# =============================================================================


def _get_new_tier_name(old_tier: str) -> str:
    """Get new tier name from old tier name."""
    return TIER_MIGRATION_MAP.get(old_tier, old_tier)


def _migrate_file(
    source_path: Path,
    dry_run: bool = True,
    force: bool = False,
) -> MigrationAction:
    """
    Migrate a single archetype file.

    Args:
        source_path: Path to source YAML file
        dry_run: If True, only report changes without modifying files
        force: If True, overwrite existing target files

    Returns:
        MigrationAction describing what was/would be done
    """
    # Extract old tier from filename
    old_tier = source_path.stem  # e.g., "low", "medium", "high", "alpha"

    # Check if already migrated
    if old_tier in ("t1", "meta", "t2_budget", "t2_optimal"):
        return MigrationAction(
            action_type="skip",
            source_path=source_path,
            changes=["Already using new tier name"],
        )

    # Check if legacy tier
    if old_tier not in TIER_MIGRATION_MAP:
        return MigrationAction(
            action_type="skip",
            source_path=source_path,
            changes=[f"Unknown tier: {old_tier}"],
        )

    # Load file
    try:
        data, content = _load_yaml_preserve_order(source_path)
    except Exception as e:
        return MigrationAction(
            action_type="skip",
            source_path=source_path,
            error=f"Failed to load YAML: {e}",
        )

    new_tier = _get_new_tier_name(old_tier)
    target_path = source_path.parent / f"{new_tier}.yaml"
    changes: list[str] = []

    # Check if target exists
    if target_path.exists() and not force:
        return MigrationAction(
            action_type="skip",
            source_path=source_path,
            target_path=target_path,
            changes=["Target file already exists (use --force to overwrite)"],
        )

    # Determine omega_required
    omega_required = _determine_omega_required(data)
    changes.append(f"skill_tier: {old_tier} -> {new_tier}")
    changes.append(f"omega_required: {omega_required}")

    # Update content
    new_content = _update_yaml_content(
        content,
        old_tier,
        new_tier,
        add_omega_required=omega_required,
    )

    if dry_run:
        return MigrationAction(
            action_type="rename",
            source_path=source_path,
            target_path=target_path,
            changes=changes,
        )

    # Perform migration
    try:
        # Write new file
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        # Remove old file (only if different from target)
        if source_path != target_path:
            source_path.unlink()

        return MigrationAction(
            action_type="rename",
            source_path=source_path,
            target_path=target_path,
            changes=changes,
        )

    except Exception as e:
        return MigrationAction(
            action_type="skip",
            source_path=source_path,
            target_path=target_path,
            error=f"Migration failed: {e}",
        )


def migrate_archetypes(
    hull: str | None = None,
    dry_run: bool = True,
    force: bool = False,
) -> MigrationResult:
    """
    Migrate all archetype files to new tier naming scheme.

    Args:
        hull: Optional hull filter (only migrate this hull's files)
        dry_run: If True, only report changes without modifying files
        force: If True, overwrite existing target files

    Returns:
        MigrationResult with details of all actions
    """
    result = MigrationResult()
    hulls_dir = get_hulls_path()

    if not hulls_dir.exists():
        logger.error("Hulls directory not found: %s", hulls_dir)
        return result

    # Find all archetype YAML files
    yaml_files: list[Path] = []

    for class_dir in hulls_dir.iterdir():
        if not class_dir.is_dir() or class_dir.name.startswith("_"):
            continue

        for hull_dir in class_dir.iterdir():
            if not hull_dir.is_dir():
                continue

            # Filter by hull if specified
            if hull and hull_dir.name.lower() != hull.lower():
                continue

            # Find all YAML files (excluding manifest)
            for yaml_file in hull_dir.rglob("*.yaml"):
                if yaml_file.name == "manifest.yaml":
                    continue
                yaml_files.append(yaml_file)

    result.total_files = len(yaml_files)

    # Migrate each file
    for yaml_file in yaml_files:
        action = _migrate_file(yaml_file, dry_run=dry_run, force=force)
        result.actions.append(action)

        if action.action_type == "rename":
            result.migrated += 1
        elif action.action_type == "skip":
            if action.error:
                result.errors += 1
            else:
                result.skipped += 1

    return result


# =============================================================================
# Update omega_required Flag
# =============================================================================


def update_omega_flags(
    hull: str | None = None,
    dry_run: bool = True,
) -> MigrationResult:
    """
    Update omega_required flags in all archetype files.

    Does not rename files, only adds/updates the omega_required field.

    Args:
        hull: Optional hull filter
        dry_run: If True, only report changes without modifying files

    Returns:
        MigrationResult with details of all actions
    """
    result = MigrationResult()
    hulls_dir = get_hulls_path()

    if not hulls_dir.exists():
        return result

    yaml_files: list[Path] = []

    for class_dir in hulls_dir.iterdir():
        if not class_dir.is_dir() or class_dir.name.startswith("_"):
            continue

        for hull_dir in class_dir.iterdir():
            if not hull_dir.is_dir():
                continue

            if hull and hull_dir.name.lower() != hull.lower():
                continue

            for yaml_file in hull_dir.rglob("*.yaml"):
                if yaml_file.name == "manifest.yaml":
                    continue
                yaml_files.append(yaml_file)

    result.total_files = len(yaml_files)

    for yaml_file in yaml_files:
        try:
            data, content = _load_yaml_preserve_order(yaml_file)

            # Check if omega_required already present
            if "omega_required" in str(content):
                result.skipped += 1
                result.actions.append(
                    MigrationAction(
                        action_type="skip",
                        source_path=yaml_file,
                        changes=["omega_required already present"],
                    )
                )
                continue

            # Determine omega_required
            omega_required = _determine_omega_required(data)
            skill_tier = data.get("archetype", {}).get("skill_tier", "")

            # Add omega_required after skill_tier
            new_content = re.sub(
                rf"(skill_tier:\s*{skill_tier})",
                f"\\1\n  omega_required: {'true' if omega_required else 'false'}",
                content,
            )

            if dry_run:
                result.migrated += 1
                result.actions.append(
                    MigrationAction(
                        action_type="update",
                        source_path=yaml_file,
                        changes=[f"Add omega_required: {omega_required}"],
                    )
                )
            else:
                with open(yaml_file, "w", encoding="utf-8") as f:
                    f.write(new_content)
                result.migrated += 1
                result.actions.append(
                    MigrationAction(
                        action_type="update",
                        source_path=yaml_file,
                        changes=[f"Added omega_required: {omega_required}"],
                    )
                )

        except Exception as e:
            result.errors += 1
            result.actions.append(
                MigrationAction(
                    action_type="skip",
                    source_path=yaml_file,
                    error=str(e),
                )
            )

    return result


# =============================================================================
# Convenience Functions
# =============================================================================


def run_migration(
    dry_run: bool = True,
    force: bool = False,
    hull: str | None = None,
) -> dict:
    """
    Run the full archetype migration.

    Args:
        dry_run: If True, only report changes without modifying files
        force: If True, overwrite existing target files
        hull: Optional hull filter

    Returns:
        Dict with migration results
    """
    logger.info(
        "Running archetype migration (dry_run=%s, force=%s, hull=%s)",
        dry_run,
        force,
        hull,
    )

    result = migrate_archetypes(hull=hull, dry_run=dry_run, force=force)

    if dry_run:
        logger.info(
            "Dry run complete: %d files to migrate, %d to skip, %d errors",
            result.migrated,
            result.skipped,
            result.errors,
        )
    else:
        logger.info(
            "Migration complete: %d files migrated, %d skipped, %d errors",
            result.migrated,
            result.skipped,
            result.errors,
        )

    return result.to_dict()
