"""
Persona Context Compiler

Compiles persona files with untrusted-data delimiters for secure LLM loading.
This is a defense-in-depth measure that wraps user-editable content in data-only
delimiters so that even if a legitimate file is compromised, its content cannot
hijack the session.

See: CLAUDE.md "Untrusted Data Handling" section

Security: Path validation added per dev/reviews/PYTHON_REVIEW_2026-01.md P0 #2
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aria_esi.core.logging import get_logger
from aria_esi.core.path_security import safe_read_persona_file

logger = get_logger(__name__)

# Maximum file size for persona content (50KB per file to avoid context bloat)
# This is stricter than the default 100KB in path_security to limit LLM context usage
PERSONA_MAX_FILE_SIZE = 50_000


@dataclass
class CompiledFile:
    """A single compiled persona file with integrity data."""

    source: str
    content: str
    size_bytes: int
    sha256: str


@dataclass
class CompiledPersonaContext:
    """Complete compiled persona context artifact."""

    version: str = "1.0"
    compiled_at: str = ""
    persona: str = ""
    branch: str = ""
    rp_level: str = ""
    files: list[CompiledFile] = field(default_factory=list)
    raw_content: str = ""  # All files concatenated with untrusted-data delimiters
    integrity: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "compiled_at": self.compiled_at,
            "persona": self.persona,
            "branch": self.branch,
            "rp_level": self.rp_level,
            "file_count": len(self.files),
            "files": [
                {
                    "source": f.source,
                    "size_bytes": f.size_bytes,
                    "sha256": f.sha256,
                }
                for f in self.files
            ],
            "raw_content": self.raw_content,
            "integrity": self.integrity,
        }


class PersonaCompiler:
    """
    Compiles persona context files with untrusted-data wrapping.

    Untrusted-data delimiters format:
    ```
    <untrusted-data source="personas/paria/voice.md">
    [file content here]
    </untrusted-data>
    ```

    This ensures the LLM treats loaded content as DATA, not instructions,
    preventing injection attacks from compromised persona files.
    """

    def __init__(self, base_path: Path):
        """
        Initialize compiler.

        Args:
            base_path: Project root path for resolving file paths
        """
        self.base_path = base_path

    def _wrap_content(self, source: str, content: str) -> str:
        """
        Wrap content with untrusted-data delimiters.

        Args:
            source: Source path for attribution
            content: Raw file content

        Returns:
            Content wrapped in untrusted-data delimiters
        """
        return f'<untrusted-data source="{source}">\n{content}\n</untrusted-data>'

    def _compute_file_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _load_and_compile_file(self, file_path: str) -> CompiledFile | None:
        """
        Load a file and compile it with untrusted-data wrapper.

        Args:
            file_path: Relative path from project root

        Returns:
            CompiledFile or None if file doesn't exist or fails security validation

        Security:
            Uses safe_read_persona_file() which enforces:
            - Directory prefix allowlist (personas/, .claude/skills/)
            - File extension allowlist (.md, .yaml, .json only)
            - File size limit (50KB per file for persona content)
            - Path traversal prevention
            - Symlink containment verification

            See dev/reviews/SECURITY_001.md Finding #1.
        """
        # Security: Use safe_read_persona_file for full validation
        # This enforces extension allowlist and size limits (Finding #1)
        content, error = safe_read_persona_file(
            file_path,
            self.base_path,
            max_size_bytes=PERSONA_MAX_FILE_SIZE,
        )

        if error:
            logger.warning("Persona file rejected: %s - %s", file_path, error)
            return None  # Graceful degradation

        wrapped = self._wrap_content(file_path, content)

        return CompiledFile(
            source=file_path,
            content=wrapped,
            size_bytes=len(content.encode("utf-8")),
            sha256=self._compute_file_hash(content),
        )

    def compile(self, persona_context: dict[str, Any]) -> CompiledPersonaContext:
        """
        Compile persona context into artifact with untrusted-data wrapping.

        Args:
            persona_context: The persona_context dict from profile

        Returns:
            CompiledPersonaContext with all files wrapped
        """
        compiled = CompiledPersonaContext(
            compiled_at=datetime.now(timezone.utc).isoformat(),
            persona=persona_context.get("persona", ""),
            branch=persona_context.get("branch", ""),
            rp_level=str(persona_context.get("rp_level", "off")),
        )

        # Compile each file
        file_paths = persona_context.get("files", [])
        raw_sections: list[str] = []

        for file_path in file_paths:
            compiled_file = self._load_and_compile_file(file_path)
            if compiled_file:
                compiled.files.append(compiled_file)
                raw_sections.append(compiled_file.content)

        # Concatenate all wrapped content
        compiled.raw_content = "\n\n".join(raw_sections)

        # Compute integrity hash of the combined content
        compiled.integrity = {
            "algorithm": "sha256",
            "hash": self._compute_file_hash(compiled.raw_content),
        }

        return compiled


def compile_persona_context(
    persona_context: dict[str, Any],
    base_path: Path,
    output_path: Path | None = None,
) -> CompiledPersonaContext:
    """
    Compile persona context and optionally write to file.

    Args:
        persona_context: The persona_context dict from profile
        base_path: Project root path
        output_path: Optional path to write compiled artifact

    Returns:
        CompiledPersonaContext
    """
    compiler = PersonaCompiler(base_path)
    compiled = compiler.compile(persona_context)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(compiled.to_dict(), f, indent=2)

    return compiled


@dataclass
class ArtifactVerificationResult:
    """Result of persona artifact integrity verification."""

    valid: bool
    artifact_exists: bool
    issues: list[str]
    verified_files: list[str]
    mismatched_files: list[str]
    missing_files: list[str]
    artifact_hash_valid: bool
    computed_hash: str | None = None
    stored_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "valid": self.valid,
            "artifact_exists": self.artifact_exists,
            "issues": self.issues,
            "verified_files": self.verified_files,
            "mismatched_files": self.mismatched_files,
            "missing_files": self.missing_files,
            "artifact_hash_valid": self.artifact_hash_valid,
            "computed_hash": self.computed_hash,
            "stored_hash": self.stored_hash,
        }


def verify_persona_artifact(
    artifact_path: Path,
    base_path: Path,
) -> ArtifactVerificationResult:
    """
    Verify integrity of a compiled persona artifact.

    Recomputes hashes from source files and compares against stored values
    to detect tampering. This is a critical security check that should run
    at session boot time.

    Security finding: SECURITY_001.md Finding #2

    Args:
        artifact_path: Path to the compiled artifact JSON
        base_path: Project root for resolving source file paths

    Returns:
        ArtifactVerificationResult with verification status and details
    """
    issues: list[str] = []
    verified_files: list[str] = []
    mismatched_files: list[str] = []
    missing_files: list[str] = []

    # Check artifact exists
    if not artifact_path.exists():
        return ArtifactVerificationResult(
            valid=False,
            artifact_exists=False,
            issues=["Compiled artifact not found"],
            verified_files=[],
            mismatched_files=[],
            missing_files=[],
            artifact_hash_valid=False,
        )

    # Load artifact
    try:
        with open(artifact_path, encoding="utf-8") as f:
            artifact = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return ArtifactVerificationResult(
            valid=False,
            artifact_exists=True,
            issues=[f"Failed to parse artifact: {e}"],
            verified_files=[],
            mismatched_files=[],
            missing_files=[],
            artifact_hash_valid=False,
        )

    # Check artifact structure
    if "files" not in artifact or "integrity" not in artifact:
        return ArtifactVerificationResult(
            valid=False,
            artifact_exists=True,
            issues=["Artifact missing required fields (files, integrity)"],
            verified_files=[],
            mismatched_files=[],
            missing_files=[],
            artifact_hash_valid=False,
        )

    stored_files = artifact.get("files", [])
    stored_integrity = artifact.get("integrity", {})
    stored_hash = stored_integrity.get("hash")
    stored_raw_content = artifact.get("raw_content", "")

    # Step 0: Verify stored raw_content matches stored integrity hash
    # This catches direct tampering of raw_content (e.g., removing delimiters)
    if stored_hash:
        actual_raw_content_hash = hashlib.sha256(
            stored_raw_content.encode("utf-8")
        ).hexdigest()
        if actual_raw_content_hash != stored_hash:
            issues.append(
                f"Raw content hash mismatch (possible tampering): "
                f"stored_integrity={stored_hash[:16]}..., "
                f"actual_raw_content={actual_raw_content_hash[:16]}..."
            )
            return ArtifactVerificationResult(
                valid=False,
                artifact_exists=True,
                issues=issues,
                verified_files=[],
                mismatched_files=[],
                missing_files=[],
                artifact_hash_valid=False,
                computed_hash=actual_raw_content_hash,
                stored_hash=stored_hash,
            )

    # Step 1: Verify individual file hashes by re-reading source files
    for file_info in stored_files:
        source = file_info.get("source")
        stored_file_hash = file_info.get("sha256")

        if not source:
            issues.append("File entry missing 'source' field")
            continue

        # Re-read the source file
        content, error = safe_read_persona_file(
            source,
            base_path,
            max_size_bytes=PERSONA_MAX_FILE_SIZE,
        )

        if error:
            if "File not found" in error:
                missing_files.append(source)
                issues.append(f"Source file missing: {source}")
            else:
                issues.append(f"Cannot read source file {source}: {error}")
            continue

        # Compute hash of current file content
        current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        if current_hash != stored_file_hash:
            mismatched_files.append(source)
            issues.append(
                f"Hash mismatch for {source}: "
                f"stored={stored_file_hash[:16]}..., current={current_hash[:16]}..."
            )
        else:
            verified_files.append(source)

    # Step 2: Verify the aggregate integrity hash
    # Recompute by re-compiling the raw_content from source files
    if verified_files or not stored_files:
        # Recompile to get expected raw_content
        raw_sections: list[str] = []
        for file_info in stored_files:
            source = file_info.get("source")
            if source in verified_files:
                content, _ = safe_read_persona_file(
                    source,
                    base_path,
                    max_size_bytes=PERSONA_MAX_FILE_SIZE,
                )
                if content:
                    wrapped = f'<untrusted-data source="{source}">\n{content}\n</untrusted-data>'
                    raw_sections.append(wrapped)

        expected_raw_content = "\n\n".join(raw_sections)
        computed_hash = hashlib.sha256(expected_raw_content.encode("utf-8")).hexdigest()

        # Check if stored raw_content matches what we'd compute
        # Also check if stored integrity hash matches
        artifact_hash_valid = stored_hash == computed_hash

        if not artifact_hash_valid and stored_hash:
            issues.append(
                f"Integrity hash mismatch: "
                f"stored={stored_hash[:16]}..., computed={computed_hash[:16]}..."
            )
    else:
        computed_hash = None
        artifact_hash_valid = False

    # Determine overall validity
    valid = (
        len(mismatched_files) == 0
        and len(missing_files) == 0
        and artifact_hash_valid
    )

    return ArtifactVerificationResult(
        valid=valid,
        artifact_exists=True,
        issues=issues,
        verified_files=verified_files,
        mismatched_files=mismatched_files,
        missing_files=missing_files,
        artifact_hash_valid=artifact_hash_valid,
        computed_hash=computed_hash,
        stored_hash=stored_hash,
    )
