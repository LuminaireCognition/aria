"""Post-execution coverage auditor for the prompt review pipeline.

Consumes prompt results from all tiers and emits coverage/coherence findings.
"""

from __future__ import annotations

from .models import SEVERITY_RANK

# Statuses that indicate the prompt was effectively skipped
_SKIPPED_STATUSES = {"skipped_not_applicable", "skipped_deferred"}

# The orchestrator's own prompt identity
_ORCHESTRATOR_PROMPT_ID = "meta.review_orchestrator"
_ORCHESTRATOR_PROMPT_PATH = "meta/review_orchestrator.md"


def run_orchestrator_check(combined_results: dict) -> dict:
    """Run the orchestrator coverage audit over combined prompt results.

    Args:
        combined_results: Merged dict with keys 'foundation', 'deep_dive', 'gate',
            each containing a list of prompt result entries, plus 'matcher' with
            matcher output including changed_files and unmatched_files.

    Returns:
        A prompt result entry conforming to prompt_results.schema.v1.
    """
    findings: list[dict] = []
    finding_counter = 0

    # Collect all prompt entries from all tiers (excluding the orchestrator itself)
    all_prompts: list[dict] = []
    for tier_key in ("foundation", "deep_dive", "gate"):
        for prompt in combined_results.get(tier_key, []):
            if prompt.get("prompt_id") != _ORCHESTRATOR_PROMPT_ID:
                all_prompts.append(prompt)

    matcher = combined_results.get("matcher", {})
    changed_files = set(matcher.get("changed_files", []))
    unmatched_files = set(matcher.get("unmatched_files", []))

    # Check if all prompts were skipped
    non_orchestrator = [p for p in all_prompts if p.get("prompt_id") != _ORCHESTRATOR_PROMPT_ID]
    all_skipped = (
        all(p.get("status") in _SKIPPED_STATUSES for p in non_orchestrator)
        if non_orchestrator
        else True
    )

    if all_skipped:
        finding_counter += 1
        findings.append(
            {
                "finding_id": f"ORCH-{finding_counter:03d}",
                "severity": "Info",
                "state": "unresolved",
                "summary": "No prompt results available for coverage audit. "
                "All non-orchestrator prompts were skipped.",
                "file_refs": [],
                "waiver_id": None,
            }
        )
        return _build_result(findings)

    # 1. Coverage gap detection
    all_file_refs: set[str] = set()
    for prompt in all_prompts:
        for finding in prompt.get("findings", []):
            for ref in finding.get("file_refs", []):
                all_file_refs.add(ref)

    coverage_gaps = (changed_files | unmatched_files) - all_file_refs
    # Only flag unmatched files that are genuinely not referenced
    for gap_file in sorted(coverage_gaps & unmatched_files):
        finding_counter += 1
        findings.append(
            {
                "finding_id": f"ORCH-{finding_counter:03d}",
                "severity": "Low",
                "state": "unresolved",
                "summary": f"Coverage gap: changed file '{gap_file}' was not addressed "
                f"by any prompt's findings.",
                "file_refs": [gap_file],
                "waiver_id": None,
            }
        )

    # 2. Silent review detection
    for prompt in all_prompts:
        status = prompt.get("status")
        prompt_findings = prompt.get("findings", [])
        if status == "success" and len(prompt_findings) == 0:
            prompt_path = prompt.get("prompt_path", "")
            # Check if any changed files overlap with this prompt's domain
            if changed_files:
                finding_counter += 1
                findings.append(
                    {
                        "finding_id": f"ORCH-{finding_counter:03d}",
                        "severity": "Info",
                        "state": "unresolved",
                        "summary": f"Silent review: prompt '{prompt_path}' produced zero "
                        f"findings despite substantive changed files.",
                        "file_refs": [],
                        "waiver_id": None,
                    }
                )

    # 3. Cross-prompt conflict detection
    file_to_findings: dict[str, list[tuple[str, dict]]] = {}
    for prompt in all_prompts:
        prompt_id = prompt.get("prompt_id", "")
        for finding in prompt.get("findings", []):
            for ref in finding.get("file_refs", []):
                file_to_findings.setdefault(ref, []).append((prompt_id, finding))

    for file_path, prompt_findings in sorted(file_to_findings.items()):
        if len(prompt_findings) < 2:
            continue
        # Check for contradictory severities from different prompts
        prompt_severities: dict[str, set[str]] = {}
        for pid, f in prompt_findings:
            prompt_severities.setdefault(pid, set()).add(f["severity"])

        if len(prompt_severities) < 2:
            continue

        severity_sets = list(prompt_severities.values())
        all_severities = set()
        for s in severity_sets:
            all_severities.update(s)

        if len(all_severities) >= 2:
            max_sev = max(all_severities, key=lambda s: SEVERITY_RANK.get(s, 0))
            min_sev = min(all_severities, key=lambda s: SEVERITY_RANK.get(s, 0))
            if SEVERITY_RANK.get(max_sev, 0) - SEVERITY_RANK.get(min_sev, 0) >= 2:
                finding_counter += 1
                prompts_involved = sorted(prompt_severities.keys())
                findings.append(
                    {
                        "finding_id": f"ORCH-{finding_counter:03d}",
                        "severity": "Medium",
                        "state": "unresolved",
                        "summary": f"Cross-prompt conflict: file '{file_path}' has findings "
                        f"with divergent severity from prompts: "
                        f"{', '.join(prompts_involved)}.",
                        "file_refs": [file_path],
                        "waiver_id": None,
                    }
                )

    # 4. Selection coherence check
    matched_rules = matcher.get("matched_rules", [])
    if changed_files and not matched_rules:
        finding_counter += 1
        findings.append(
            {
                "finding_id": f"ORCH-{finding_counter:03d}",
                "severity": "Medium",
                "state": "unresolved",
                "summary": "Selection anomaly: changed files present but no matcher rules matched.",
                "file_refs": [],
                "waiver_id": None,
            }
        )

    return _build_result(findings)


def _build_result(findings: list[dict]) -> dict:
    """Build a standard schema v1 prompt result entry for the orchestrator."""
    return {
        "prompt_id": _ORCHESTRATOR_PROMPT_ID,
        "prompt_instance_id": f"{_ORCHESTRATOR_PROMPT_ID}@default",
        "prompt_path": _ORCHESTRATOR_PROMPT_PATH,
        "tier": "foundation",
        "selection_reason": "foundation_trigger",
        "selection_trace": [
            {
                "tier": "foundation",
                "selection_reason": "foundation_trigger",
                "matched_by": "rule_id",
                "rule_id": "foundation.core_surfaces.v1",
            }
        ],
        "status": "success",
        "not_applicable_reason": None,
        "duration_ms": 0,
        "findings": findings,
    }
