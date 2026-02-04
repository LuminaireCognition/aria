"""
Archetype Validation Module.

Provides validation for archetype files including schema validation,
alpha clone restrictions, and EOS fit validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .loader import (
    ArchetypeLoader,
    list_archetypes,
)
from .models import Archetype, HullManifest

if TYPE_CHECKING:
    pass


# =============================================================================
# Validation Result
# =============================================================================


@dataclass
class ValidationIssue:
    """
    A single validation issue.
    """

    level: str  # "error", "warning", "info"
    category: str  # "schema", "alpha", "eos", "consistency"
    message: str
    path: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "level": self.level,
            "category": self.category,
            "message": self.message,
            "path": self.path,
        }


@dataclass
class ValidationResult:
    """
    Result of archetype validation.
    """

    path: str
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    archetype: Archetype | None = None
    manifest: HullManifest | None = None

    @property
    def errors(self) -> list[ValidationIssue]:
        """Get error-level issues."""
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get warning-level issues."""
        return [i for i in self.issues if i.level == "warning"]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [i.to_dict() for i in self.issues],
        }


# =============================================================================
# Alpha Clone Validation
# =============================================================================

# Patterns that indicate T2 modules (forbidden for alpha)
T2_MODULE_PATTERNS = [
    r" II$",  # Standard T2 suffix
]

# Specific modules forbidden for alpha clones
ALPHA_FORBIDDEN_MODULES = [
    "Siege Module",
    "Bastion Module",
    "Triage Module",
    "Industrial Core",
]

# Ship patterns forbidden for alpha
ALPHA_FORBIDDEN_SHIPS = [
    r"^Marauder",
    r"^Strategic Cruiser",
    r"^Black Ops",
    r"^Command Ship",
    r"^Heavy Assault Cruiser",
    r"^Logistics Cruiser",
    r"^Force Recon",
    r"^Combat Recon",
]


def _check_alpha_restrictions(eft: str) -> list[ValidationIssue]:
    """
    Check if EFT contains modules forbidden for alpha clones.

    Args:
        eft: EFT format string

    Returns:
        List of validation issues
    """
    issues = []
    lines = eft.strip().split("\n")

    for line in lines:
        stripped = line.strip()

        # Skip empty lines and slot markers
        if not stripped or stripped.startswith("[Empty") or stripped.startswith("["):
            continue

        # Check for T2 modules
        for pattern in T2_MODULE_PATTERNS:
            if re.search(pattern, stripped):
                issues.append(
                    ValidationIssue(
                        level="error",
                        category="alpha",
                        message=f"T2 module not allowed for alpha: {stripped}",
                    )
                )
                break

        # Check for specific forbidden modules
        for forbidden in ALPHA_FORBIDDEN_MODULES:
            if forbidden.lower() in stripped.lower():
                issues.append(
                    ValidationIssue(
                        level="error",
                        category="alpha",
                        message=f"Module not allowed for alpha: {stripped}",
                    )
                )
                break

    return issues


def _check_alpha_ship(eft: str) -> list[ValidationIssue]:
    """
    Check if ship type is allowed for alpha clones.

    Args:
        eft: EFT format string

    Returns:
        List of validation issues
    """
    issues = []

    # Parse ship name from header
    lines = eft.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and "]" in stripped:
            content = stripped[1:].split("]")[0]
            ship = content.split(",")[0].strip()

            for pattern in ALPHA_FORBIDDEN_SHIPS:
                if re.match(pattern, ship, re.IGNORECASE):
                    issues.append(
                        ValidationIssue(
                            level="error",
                            category="alpha",
                            message=f"Ship not allowed for alpha: {ship}",
                        )
                    )
            break

    return issues


# =============================================================================
# Schema Validation
# =============================================================================


def _validate_schema(archetype: Archetype, path: str) -> list[ValidationIssue]:
    """
    Validate archetype against expected schema.

    Args:
        archetype: Archetype to validate
        path: Path string for context

    Returns:
        List of validation issues
    """
    issues = []

    # Required fields
    if not archetype.eft:
        issues.append(
            ValidationIssue(
                level="error",
                category="schema",
                message="Missing required field: eft",
                path=path,
            )
        )

    if not archetype.archetype.hull:
        issues.append(
            ValidationIssue(
                level="error",
                category="schema",
                message="Missing required field: archetype.hull",
                path=path,
            )
        )

    if not archetype.archetype.skill_tier:
        issues.append(
            ValidationIssue(
                level="error",
                category="schema",
                message="Missing required field: archetype.skill_tier",
                path=path,
            )
        )

    # Validate skill tier value (accept both old and new tier names)
    valid_tiers = {
        # New tier names
        "t1",
        "meta",
        "t2_budget",
        "t2_optimal",
        # Legacy tier names (for backward compatibility)
        "low",
        "medium",
        "high",
        "alpha",
    }
    if archetype.archetype.skill_tier not in valid_tiers:
        issues.append(
            ValidationIssue(
                level="error",
                category="schema",
                message=f"Invalid skill_tier: {archetype.archetype.skill_tier}. Expected one of: {valid_tiers}",
                path=path,
            )
        )

    # Warn about legacy tier names
    legacy_tiers = {"low", "medium", "high", "alpha"}
    if archetype.archetype.skill_tier in legacy_tiers:
        issues.append(
            ValidationIssue(
                level="warning",
                category="schema",
                message=f"Legacy skill_tier '{archetype.archetype.skill_tier}' - consider migrating to new tier names",
                path=path,
            )
        )

    # Validate EFT format
    if archetype.eft:
        eft_lines = archetype.eft.strip().split("\n")
        if not eft_lines or not eft_lines[0].strip().startswith("["):
            issues.append(
                ValidationIssue(
                    level="error",
                    category="schema",
                    message="EFT must start with [Ship, Name] header",
                    path=path,
                )
            )

    # Validate stats
    if archetype.stats:
        if archetype.stats.dps < 0:
            issues.append(
                ValidationIssue(
                    level="error",
                    category="schema",
                    message=f"Invalid stats.dps: {archetype.stats.dps} (must be >= 0)",
                    path=path,
                )
            )
        if archetype.stats.ehp < 0:
            issues.append(
                ValidationIssue(
                    level="error",
                    category="schema",
                    message=f"Invalid stats.ehp: {archetype.stats.ehp} (must be >= 0)",
                    path=path,
                )
            )

    return issues


# =============================================================================
# Omega/T2 Consistency Validation
# =============================================================================


def _has_t2_modules(eft: str) -> bool:
    """
    Check if EFT contains T2 modules.

    T2 modules end with " II" (space + Roman numeral 2).

    Args:
        eft: EFT format string

    Returns:
        True if any T2 modules are present
    """
    for line in eft.strip().split("\n"):
        stripped = line.strip()
        # Skip empty lines, slot markers, and header
        if not stripped or stripped.startswith("["):
            continue
        # Check for T2 suffix
        if re.search(r" II$", stripped):
            return True
        # Also check for module with charge: "Module II, Charge"
        if re.search(r" II,", stripped):
            return True
    return False


def _validate_omega_consistency(
    archetype: Archetype,
    path: str,
) -> list[ValidationIssue]:
    """
    Validate omega_required flag consistency with T2 module usage.

    If omega_required is False but fit contains T2 modules, emit warning
    since alpha clones cannot use T2 modules.

    Args:
        archetype: Archetype to validate
        path: Path string for context

    Returns:
        List of validation issues
    """
    issues = []

    if not archetype.archetype.omega_required:
        if _has_t2_modules(archetype.eft):
            issues.append(
                ValidationIssue(
                    level="warning",
                    category="consistency",
                    message=(
                        "omega_required=false but fit contains T2 modules. "
                        "Alpha clones cannot use T2 modules. "
                        "Consider setting omega_required=true or replacing T2 modules."
                    ),
                    path=path,
                )
            )

    return issues


# =============================================================================
# Consistency Validation
# =============================================================================


def _validate_consistency(
    archetype: Archetype,
    manifest: HullManifest | None,
    path: str,
) -> list[ValidationIssue]:
    """
    Validate consistency between archetype and manifest.

    Args:
        archetype: Archetype to validate
        manifest: Hull manifest (may be None)
        path: Path string for context

    Returns:
        List of validation issues
    """
    issues = []

    if not manifest:
        issues.append(
            ValidationIssue(
                level="warning",
                category="consistency",
                message=f"No manifest found for hull: {archetype.archetype.hull}",
                path=path,
            )
        )
        return issues

    # Check hull name matches
    if archetype.archetype.hull.lower() != manifest.hull.lower():
        issues.append(
            ValidationIssue(
                level="error",
                category="consistency",
                message=f"Hull mismatch: archetype says '{archetype.archetype.hull}', manifest says '{manifest.hull}'",
                path=path,
            )
        )

    # Check tank profile if damage_tuning exists
    if archetype.damage_tuning:
        if archetype.damage_tuning.tank_profile != manifest.fitting_rules.tank_type:
            issues.append(
                ValidationIssue(
                    level="warning",
                    category="consistency",
                    message=f"Tank profile mismatch: archetype uses '{archetype.damage_tuning.tank_profile}', "
                    f"manifest recommends '{manifest.fitting_rules.tank_type}'",
                    path=path,
                )
            )

    return issues


# =============================================================================
# EOS Validation (Optional)
# =============================================================================


def _validate_with_eos(archetype: Archetype, path: str) -> list[ValidationIssue]:
    """
    Validate archetype fit using EOS fitting engine.

    Args:
        archetype: Archetype to validate
        path: Path string for context

    Returns:
        List of validation issues
    """
    issues = []

    try:
        # Try to import EOS components
        from aria_esi.fitting import get_eos_data_manager
        from aria_esi.fitting.eft_parser import parse_eft

        data_manager = get_eos_data_manager()
        status = data_manager.validate()

        if not status.is_valid:
            issues.append(
                ValidationIssue(
                    level="warning",
                    category="eos",
                    message="EOS data not available - skipping EOS validation",
                    path=path,
                )
            )
            return issues

        # Parse the EFT to verify it's valid
        try:
            parsed = parse_eft(archetype.eft)
            if not parsed:
                issues.append(
                    ValidationIssue(
                        level="error",
                        category="eos",
                        message="Failed to parse EFT format",
                        path=path,
                    )
                )
                return issues

            # Basic validation passed - EFT is parseable
            # Full stats calculation requires async context (MCP server)
            # For now, we just verify the fit parses correctly
            issues.append(
                ValidationIssue(
                    level="info",
                    category="eos",
                    message=f"EFT parsed successfully: {parsed.ship_type_name} with {len(parsed.low_slots) + len(parsed.mid_slots) + len(parsed.high_slots)} modules",
                    path=path,
                )
            )

            # Note: Full stats comparison (DPS, EHP, CPU/PG) requires async MCP context.
            # The EOS fitting MCP tool provides this, but can't be called from sync code.
            # For now, we verify the EFT is parseable. Stats drift detection is a future enhancement.

        except Exception as e:
            issues.append(
                ValidationIssue(
                    level="error",
                    category="eos",
                    message=f"EOS validation failed: {str(e)}",
                    path=path,
                )
            )

    except ImportError:
        issues.append(
            ValidationIssue(
                level="info",
                category="eos",
                message="EOS fitting module not available - skipping EOS validation",
                path=path,
            )
        )

    return issues


# =============================================================================
# Main Validator Class
# =============================================================================


class ArchetypeValidator:
    """
    Validates archetype files.
    """

    def __init__(self, use_eos: bool = False):
        """
        Initialize validator.

        Args:
            use_eos: Whether to use EOS for fit validation
        """
        self.use_eos = use_eos
        self._loader = ArchetypeLoader()

    def validate_archetype(self, path: str) -> ValidationResult:
        """
        Validate a single archetype.

        Args:
            path: Archetype path string (e.g., "vexor/pve/missions/l2/medium")

        Returns:
            ValidationResult
        """
        result = ValidationResult(path=path, is_valid=True)

        # Load archetype
        archetype = self._loader.get_archetype(path)
        if not archetype:
            result.is_valid = False
            result.issues.append(
                ValidationIssue(
                    level="error",
                    category="schema",
                    message=f"Archetype not found: {path}",
                    path=path,
                )
            )
            return result

        result.archetype = archetype

        # Load manifest
        manifest = self._loader.get_manifest(archetype.archetype.hull)
        result.manifest = manifest

        # Schema validation
        result.issues.extend(_validate_schema(archetype, path))

        # Alpha restrictions (only for alpha tier)
        if archetype.archetype.skill_tier == "alpha":
            result.issues.extend(_check_alpha_restrictions(archetype.eft))
            result.issues.extend(_check_alpha_ship(archetype.eft))

        # Consistency validation
        result.issues.extend(_validate_consistency(archetype, manifest, path))

        # Omega/T2 consistency validation
        result.issues.extend(_validate_omega_consistency(archetype, path))

        # EOS validation (optional)
        if self.use_eos:
            result.issues.extend(_validate_with_eos(archetype, path))

        # Determine overall validity
        result.is_valid = len(result.errors) == 0

        return result

    def validate_all(self, hull: str | None = None) -> list[ValidationResult]:
        """
        Validate all archetypes.

        Args:
            hull: Optional hull filter

        Returns:
            List of ValidationResults
        """
        results = []
        paths = list_archetypes(hull)

        for path in paths:
            result = self.validate_archetype(path)
            results.append(result)

        return results

    def validate_manifest(self, hull: str) -> ValidationResult:
        """
        Validate a hull manifest.

        Args:
            hull: Hull name

        Returns:
            ValidationResult
        """
        result = ValidationResult(path=f"{hull}/manifest.yaml", is_valid=True)

        manifest = self._loader.get_manifest(hull)
        if not manifest:
            result.is_valid = False
            result.issues.append(
                ValidationIssue(
                    level="error",
                    category="schema",
                    message=f"Manifest not found for hull: {hull}",
                )
            )
            return result

        result.manifest = manifest

        # Validate required fields
        if not manifest.hull:
            result.issues.append(
                ValidationIssue(
                    level="error",
                    category="schema",
                    message="Missing required field: hull",
                )
            )

        if not manifest.ship_class:
            result.issues.append(
                ValidationIssue(
                    level="error",
                    category="schema",
                    message="Missing required field: class",
                )
            )

        # Validate slot counts
        if manifest.slots:
            total_slots = (
                manifest.slots.high + manifest.slots.mid + manifest.slots.low + manifest.slots.rig
            )
            if total_slots == 0:
                result.issues.append(
                    ValidationIssue(
                        level="warning",
                        category="schema",
                        message="All slot counts are zero - may be missing data",
                    )
                )

        result.is_valid = len(result.errors) == 0
        return result


# =============================================================================
# Convenience Functions
# =============================================================================


def validate_archetype(path: str, use_eos: bool = False) -> ValidationResult:
    """
    Validate a single archetype.

    Args:
        path: Archetype path string
        use_eos: Whether to use EOS validation

    Returns:
        ValidationResult
    """
    validator = ArchetypeValidator(use_eos=use_eos)
    return validator.validate_archetype(path)


def validate_all_archetypes(
    hull: str | None = None,
    use_eos: bool = False,
) -> list[ValidationResult]:
    """
    Validate all archetypes.

    Args:
        hull: Optional hull filter
        use_eos: Whether to use EOS validation

    Returns:
        List of ValidationResults
    """
    validator = ArchetypeValidator(use_eos=use_eos)
    return validator.validate_all(hull)
