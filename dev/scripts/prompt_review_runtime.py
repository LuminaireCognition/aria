#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from aria_esi.prompt_review.matcher import select_prompts


def _git_changed_files(event: str, base_sha: str | None, head_sha: str | None) -> tuple[list[str], str, str | None, str | None]:
    if base_sha and head_sha:
        cmd = ["git", "diff", "--name-only", f"{base_sha}..{head_sha}"]
        try:
            output = subprocess.check_output(cmd, text=True)
            return [line.strip() for line in output.splitlines() if line.strip()], "normal", None, None
        except subprocess.CalledProcessError:
            if event == "pull_request":
                return [], "fail_closed", "missing_or_unfetchable_shas", None
            return [], "normal", None, None
    if event == "push" and head_sha and not base_sha:
        cmd = ["git", "ls-tree", "-r", "--name-only", head_sha]
        output = subprocess.check_output(cmd, text=True)
        return [line.strip() for line in output.splitlines() if line.strip()], "before_missing_fallback", None, "all_files_changed"
    elif event in {"workflow_dispatch", "schedule"} and not (base_sha and head_sha):
        return [], "not_applicable", None, None
    else:
        return [], "normal", None, None


def _normalize_proposal_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    normalized = str(Path(normalized).as_posix())
    return normalized.lstrip("./").rstrip("/")


def _validate_manual_proposal_path(path: str) -> tuple[str | None, str | None]:
    normalized = _normalize_proposal_path(path)
    if not normalized or normalized.startswith("/") or ".." in Path(normalized).parts:
        return None, "invalid_proposal_path"
    if not normalized.startswith("dev/proposals/") or not normalized.endswith(".md"):
        return None, "invalid_proposal_path"
    if normalized.startswith("dev/proposals/archive/"):
        return None, "invalid_proposal_path"
    resolved = (Path.cwd() / normalized).resolve()
    try:
        resolved.relative_to(Path.cwd().resolve())
    except ValueError:
        return None, "invalid_proposal_path"
    return normalized, None


def _proposal_paths(changed_files: list[str], event: str, manual_path: str | None) -> tuple[list[str], str | None]:
    if manual_path:
        normalized, error = _validate_manual_proposal_path(manual_path)
        if error or normalized is None:
            return [], error
        return [normalized], None
    if event != "pull_request":
        return [], None
    return (
        [
            path
            for path in changed_files
            if path.startswith("dev/proposals/") and path.endswith(".md") and not path.startswith("dev/proposals/archive/")
        ],
        None,
    )


def _gate_not_applicable_entry(
    *,
    prompt_id: str,
    prompt_path: str,
    reason: str,
    proposal_path: str | None = None,
) -> dict:
    rule_ids = {
        "dev/proposal_implementation_readiness.md": "gate.proposal_implementation_readiness.v1",
        "dev/premerge.md": "gate.premerge.v1",
        "dev/postmerge_regression_audit.md": "gate.postmerge_regression_audit.v1",
    }
    instance = f"{prompt_id}@default"
    if proposal_path:
        instance = f"{prompt_id}@proposal:{quote(proposal_path, safe='/')}"
    return {
        "prompt_id": prompt_id,
        "prompt_instance_id": instance,
        "prompt_path": prompt_path,
        "tier": "gate",
        "selection_reason": "gate_trigger",
        "selection_trace": [
            {
                "tier": "gate",
                "selection_reason": "gate_trigger",
                "matched_by": "gate_policy",
                "rule_id": rule_ids[prompt_path],
            }
        ],
        "status": "skipped_not_applicable",
        "not_applicable_reason": reason,
        "duration_ms": 0,
        "findings": [],
    }


def _select_explicit_gates(proposal_path: str | None, invalid_gate_input: bool) -> list[dict]:
    prompts: list[dict] = []
    premerge_id = "dev.premerge"
    proposal_id = "dev.proposal_implementation_readiness"
    postmerge_id = "dev.postmerge_regression_audit"
    if invalid_gate_input:
        prompts.append(
            _gate_not_applicable_entry(
                prompt_id=proposal_id,
                prompt_path="dev/proposal_implementation_readiness.md",
                reason="invalid_gate_input",
            )
        )
        prompts.append(
            _gate_not_applicable_entry(
                prompt_id=premerge_id,
                prompt_path="dev/premerge.md",
                reason="event_not_supported",
            )
        )
        return prompts

    if proposal_path:
        prompts.append(
            {
                "prompt_id": proposal_id,
                "prompt_instance_id": f"{proposal_id}@proposal:{quote(proposal_path, safe='/')}",
                "prompt_path": "dev/proposal_implementation_readiness.md",
                "tier": "gate",
                "selection_reason": "gate_trigger",
                "selection_trace": [
                    {
                        "tier": "gate",
                        "selection_reason": "gate_trigger",
                        "matched_by": "gate_policy",
                        "rule_id": "gate.proposal_implementation_readiness.v1",
                    }
                ],
                "status": "success",
                "not_applicable_reason": None,
                "duration_ms": 0,
                "findings": [],
            }
        )
    else:
        prompts.append(
            _gate_not_applicable_entry(
                prompt_id=proposal_id,
                prompt_path="dev/proposal_implementation_readiness.md",
                reason="no_gate_input",
            )
        )
    prompts.append(
        _gate_not_applicable_entry(
            prompt_id=premerge_id,
            prompt_path="dev/premerge.md",
            reason="event_not_supported",
        )
    )
    prompts.append(
        _gate_not_applicable_entry(
            prompt_id=postmerge_id,
            prompt_path="dev/postmerge_regression_audit.md",
            reason="event_not_supported",
        )
    )
    return prompts


def _summary_for(prompts: list[dict]) -> dict:
    return {
        "by_severity": {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0},
        "by_state": {"unresolved": 0, "resolved": 0, "waived": 0},
        "total_findings": 0,
        "total_prompts": len(prompts),
    }


def _emit_combined(
    *,
    event: str,
    base_sha: str | None,
    head_sha: str | None,
    prompts: list[dict],
    matcher: dict,
    gate_decision: str,
) -> int:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    combined = {
        "schema_version": "v1",
        "run_context": {
            "event": event,
            "base_sha": base_sha,
            "head_sha": head_sha,
            "ref": os.getenv("GITHUB_REF", ""),
            "pr_number": int(os.getenv("PR_NUMBER") or "0") or None,
            "generated_at_utc": now,
        },
        "matcher": matcher,
        "prompts": prompts,
        "summary": _summary_for(prompts),
        "gate_decision": gate_decision,
    }

    output = Path("artifacts/prompt-results/combined.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    event = os.getenv("PROMPT_EVENT", "pull_request")
    base_sha = os.getenv("PROMPT_BASE_SHA")
    head_sha = os.getenv("PROMPT_HEAD_SHA")
    manual_proposal = os.getenv("PROPOSAL_PATH")
    postmerge_applicable = os.getenv("POSTMERGE_APPLICABLE", "false").lower() == "true"
    postmerge_target_sha = os.getenv("POSTMERGE_TARGET_SHA")

    allowed_gate_inputs = {"PROPOSAL_PATH", "POSTMERGE_TARGET_SHA", "POSTMERGE_PR_NUMBER"}
    invalid_gate_input = any(
        key.startswith("GATE_INPUT_") and key.removeprefix("GATE_INPUT_") not in allowed_gate_inputs for key in os.environ
    )

    changed_files, matcher_mode, matcher_error, before_missing_fallback = _git_changed_files(event, base_sha, head_sha)
    proposal_paths, proposal_error = _proposal_paths(changed_files, event, manual_proposal)

    if event == "pull_request" and matcher_mode == "fail_closed":
        return _emit_combined(
            event=event,
            base_sha=base_sha,
            head_sha=head_sha,
            prompts=[],
            matcher={
                "changed_files": [],
                "case_sensitive": True,
                "rename_mode": "old_and_new",
                "delete_mode": "include_deleted_path",
                "mode": "fail_closed",
                "error_code": "missing_or_unfetchable_shas",
                "unmatched_files": [],
                "matched_rules": [],
                "before_missing_fallback": None,
            },
            gate_decision="fail",
        )

    if event in {"workflow_dispatch", "schedule"} and matcher_mode == "not_applicable":
        proposal_path = proposal_paths[0] if proposal_paths else None
        prompts = _select_explicit_gates(proposal_path if proposal_error is None else None, invalid_gate_input)
        if proposal_error:
            prompts = [
                _gate_not_applicable_entry(
                    prompt_id="dev.proposal_implementation_readiness",
                    prompt_path="dev/proposal_implementation_readiness.md",
                    reason=proposal_error,
                ),
                _gate_not_applicable_entry(
                    prompt_id="dev.premerge",
                    prompt_path="dev/premerge.md",
                    reason="event_not_supported",
                ),
                _gate_not_applicable_entry(
                    prompt_id="dev.postmerge_regression_audit",
                    prompt_path="dev/postmerge_regression_audit.md",
                    reason="event_not_supported",
                ),
            ]
        return _emit_combined(
            event=event,
            base_sha=base_sha,
            head_sha=head_sha,
            prompts=prompts,
            matcher={
                "changed_files": [],
                "case_sensitive": True,
                "rename_mode": "old_and_new",
                "delete_mode": "include_deleted_path",
                "mode": "not_applicable",
                "error_code": None,
                "unmatched_files": [],
                "matched_rules": [],
                "before_missing_fallback": None,
            },
            gate_decision="pass",
        )

    if postmerge_target_sha and event not in {"push", "workflow_dispatch"}:
        invalid_gate_input = True

    selection = select_prompts(
        config_path="dev/policy/prompt_matcher_rules.yaml",
        event=event,
        changed_files=changed_files,
        proposal_paths=proposal_paths,
        postmerge_applicable=postmerge_applicable,
    )

    prompt_tier = os.getenv("PROMPT_TIER")

    prompts = []
    for selected in selection["selected"]:
        prompts.append(
            {
                **selected,
                "not_applicable_reason": None,
                "status": "success",
                "duration_ms": 0,
                "findings": [],
            }
        )
    for skipped in selection["skipped_deferred"]:
        prompt_id = skipped["prompt_path"].replace("/", ".").removesuffix(".md")
        prompts.append(
            {
                "prompt_id": prompt_id,
                "prompt_instance_id": f"{prompt_id}@default",
                "prompt_path": skipped["prompt_path"],
                "tier": "deep_dive",
                "selection_reason": skipped["selection_reason"],
                "selection_trace": [
                    {
                        "tier": "deep_dive",
                        "selection_reason": skipped["selection_reason"],
                        "matched_by": "rule_id",
                        "rule_id": skipped["rule_id"],
                    }
                ],
                "status": "skipped_deferred",
                "not_applicable_reason": None,
                "duration_ms": 0,
                "findings": [],
            }
        )
    if invalid_gate_input:
        prompts.append(
            _gate_not_applicable_entry(
                prompt_id="dev.proposal_implementation_readiness",
                prompt_path="dev/proposal_implementation_readiness.md",
                reason="invalid_gate_input",
            )
        )

    # Tier isolation: filter prompts to requested tier
    if prompt_tier:
        _TIER_MAP = {
            "foundation": {"foundation"},
            "deep_dive": {"deep_dive", "fallback"},
            "gate": {"gate"},
        }
        allowed_tiers = _TIER_MAP.get(prompt_tier, set())
        if prompt_tier == "foundation":
            # Foundation tier also includes skipped_deferred entries
            prompts = [
                p for p in prompts
                if p["tier"] in allowed_tiers or p.get("status") == "skipped_deferred"
            ]
        else:
            prompts = [p for p in prompts if p["tier"] in allowed_tiers]

    return _emit_combined(
        event=event,
        base_sha=base_sha,
        head_sha=head_sha,
        prompts=prompts,
        matcher={
            "changed_files": selection["changed_files"],
            "case_sensitive": True,
            "rename_mode": "old_and_new",
            "delete_mode": "include_deleted_path",
            "mode": matcher_mode,
            "error_code": matcher_error,
            "unmatched_files": selection["unmatched_files"],
            "matched_rules": selection["matched_rules"],
            "before_missing_fallback": before_missing_fallback,
        },
        gate_decision="pass",
    )


if __name__ == "__main__":
    sys.exit(main())
