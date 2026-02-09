from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import PurePosixPath
from urllib.parse import quote

import yaml

from .models import TIER_PRECEDENCE, PromptSelection

VALID_EVENTS = {"pull_request", "push", "workflow_dispatch", "schedule"}


def _match_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in patterns)


def _normalize(path: str) -> str:
    return str(PurePosixPath(path))


def _prompt_id_from_path(prompt_path: str) -> str:
    return prompt_path.replace("/", ".").removesuffix(".md")


def _instance_id(prompt_id: str, proposal_path: str | None = None) -> str:
    if proposal_path:
        normalized = _normalize(proposal_path).lstrip("./").rstrip("/")
        encoded = quote(normalized, safe="/")
        return f"{prompt_id}@proposal:{encoded}"
    return f"{prompt_id}@default"


def _dedup_by_precedence(selections: list[PromptSelection]) -> list[PromptSelection]:
    by_instance: dict[tuple[str, str], PromptSelection] = {}
    for selection in selections:
        key = (selection.prompt_path, selection.prompt_instance_id)
        existing = by_instance.get(key)
        if existing is None:
            by_instance[key] = selection
            continue
        winner = existing
        loser = selection
        if TIER_PRECEDENCE[selection.tier] < TIER_PRECEDENCE[existing.tier]:
            winner = selection
            loser = existing
        trace = winner.selection_trace + loser.selection_trace
        deduped_trace: list[dict] = []
        seen: set[tuple[str, str, str, str | None]] = set()
        for entry in sorted(
            trace,
            key=lambda e: (
                TIER_PRECEDENCE[e["tier"]],
                e["selection_reason"],
                e["matched_by"],
                e.get("rule_id") or "",
            ),
        ):
            sig = (entry["tier"], entry["selection_reason"], entry["matched_by"], entry.get("rule_id"))
            if sig in seen:
                continue
            seen.add(sig)
            deduped_trace.append(entry)
        by_instance[key] = PromptSelection(
            prompt_id=winner.prompt_id,
            prompt_instance_id=winner.prompt_instance_id,
            prompt_path=winner.prompt_path,
            tier=winner.tier,
            selection_reason=winner.selection_reason,
            selection_trace=deduped_trace,
        )
    return sorted(
        by_instance.values(),
        key=lambda s: (TIER_PRECEDENCE[s.tier], s.prompt_path, s.prompt_instance_id),
    )


def select_prompts(
    *,
    config_path: str,
    event: str,
    changed_files: list[str],
    proposal_paths: list[str] | None = None,
    postmerge_applicable: bool = False,
) -> dict:
    """Select prompts deterministically from changed files and event context."""
    if event not in VALID_EVENTS:
        raise ValueError(f"unsupported event: {event}")

    with open(config_path, encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    normalized_changed = [_normalize(path) for path in changed_files]
    matched_files: set[str] = set()
    matched_rules: set[str] = set()

    selections: list[PromptSelection] = []
    skipped_deferred: list[dict[str, str]] = []

    foundation_patterns = config["foundation"]["triggers"]
    foundation_rule_id = config["foundation"]["rule_id"]
    if any(_match_any(path, foundation_patterns) for path in normalized_changed):
        matched_rules.add(foundation_rule_id)
        for path in normalized_changed:
            if _match_any(path, foundation_patterns):
                matched_files.add(path)
        for prompt_path in config["foundation"]["prompt_paths"]:
            prompt_id = _prompt_id_from_path(prompt_path)
            selections.append(
                PromptSelection(
                    prompt_id=prompt_id,
                    prompt_instance_id=_instance_id(prompt_id),
                    prompt_path=prompt_path,
                    tier="foundation",
                    selection_reason="foundation_trigger",
                    selection_trace=[
                        {
                            "tier": "foundation",
                            "selection_reason": "foundation_trigger",
                            "matched_by": "rule_id",
                            "rule_id": foundation_rule_id,
                        }
                    ],
                )
            )

    active_deep_dive = False
    deferred_hit = False
    for rule in config["deep_dive"]:
        rule_id = rule["rule_id"]
        if not any(_match_any(path, rule["triggers"]) for path in normalized_changed):
            continue
        matched_rules.add(rule_id)
        for path in normalized_changed:
            if _match_any(path, rule["triggers"]):
                matched_files.add(path)
        if rule.get("deferred", False):
            deferred_hit = True
            skipped_deferred.append(
                {
                    "prompt_path": rule["prompt_path"],
                    "status": "skipped_deferred",
                    "selection_reason": "deferred_fallback",
                    "rule_id": rule_id,
                }
            )
            continue
        active_deep_dive = True
        prompt_path = rule["prompt_path"]
        prompt_id = _prompt_id_from_path(prompt_path)
        selections.append(
                PromptSelection(
                    prompt_id=prompt_id,
                    prompt_instance_id=_instance_id(prompt_id),
                    prompt_path=prompt_path,
                    tier="deep_dive",
                    selection_reason="deep_dive_trigger",
                    selection_trace=[
                        {
                            "tier": "deep_dive",
                            "selection_reason": "deep_dive_trigger",
                            "matched_by": "rule_id",
                            "rule_id": rule_id,
                        }
                    ],
                )
            )

    if deferred_hit or not active_deep_dive:
        fallback_reason = "deferred_fallback" if deferred_hit else "global_fallback"
        fallback_rule_id = config["fallback"][event]["rule_id"]
        matched_rules.add(fallback_rule_id)
        for prompt_path in config["fallback"][event]["prompt_paths"]:
            prompt_id = _prompt_id_from_path(prompt_path)
            selections.append(
                PromptSelection(
                    prompt_id=prompt_id,
                    prompt_instance_id=_instance_id(prompt_id),
                    prompt_path=prompt_path,
                    tier="fallback",
                    selection_reason=fallback_reason,
                    selection_trace=[
                        {
                            "tier": "fallback",
                            "selection_reason": fallback_reason,
                            "matched_by": "rule_id",
                            "rule_id": fallback_rule_id,
                        }
                    ],
                )
            )

    # Gate prompts
    for gate_rule in config["gate"]["rules"]:
        prompt_path = gate_rule["prompt_path"]
        gate_rule_id = gate_rule["rule_id"]
        prompt_id = _prompt_id_from_path(prompt_path)
        if prompt_path == "dev/premerge.md":
            status = event == "pull_request"
            if status:
                selections.append(
                    PromptSelection(
                        prompt_id=prompt_id,
                        prompt_instance_id=_instance_id(prompt_id),
                        prompt_path=prompt_path,
                        tier="gate",
                        selection_reason="gate_trigger",
                        selection_trace=[
                            {
                                "tier": "gate",
                                "selection_reason": "gate_trigger",
                                "matched_by": "gate_policy",
                                "rule_id": gate_rule_id,
                            }
                        ],
                    )
                )
            continue

        if prompt_path == "dev/proposal_implementation_readiness.md":
            if event == "pull_request" and proposal_paths:
                for proposal_path in proposal_paths:
                    selections.append(
                        PromptSelection(
                            prompt_id=prompt_id,
                            prompt_instance_id=_instance_id(prompt_id, proposal_path),
                            prompt_path=prompt_path,
                            tier="gate",
                            selection_reason="gate_trigger",
                            selection_trace=[
                                {
                                    "tier": "gate",
                                    "selection_reason": "gate_trigger",
                                    "matched_by": "gate_policy",
                                    "rule_id": gate_rule_id,
                                }
                            ],
                        )
                    )
            elif event in {"workflow_dispatch", "schedule"} and proposal_paths:
                for proposal_path in proposal_paths:
                    selections.append(
                        PromptSelection(
                            prompt_id=prompt_id,
                            prompt_instance_id=_instance_id(prompt_id, proposal_path),
                            prompt_path=prompt_path,
                            tier="gate",
                            selection_reason="gate_trigger",
                            selection_trace=[
                                {
                                    "tier": "gate",
                                    "selection_reason": "gate_trigger",
                                    "matched_by": "gate_policy",
                                    "rule_id": gate_rule_id,
                                }
                            ],
                        )
                    )
            continue

        if prompt_path == "dev/postmerge_regression_audit.md" and postmerge_applicable:
            selections.append(
                PromptSelection(
                    prompt_id=prompt_id,
                    prompt_instance_id=_instance_id(prompt_id),
                    prompt_path=prompt_path,
                    tier="gate",
                    selection_reason="postmerge_policy",
                    selection_trace=[
                        {
                            "tier": "gate",
                            "selection_reason": "postmerge_policy",
                            "matched_by": "gate_policy",
                            "rule_id": gate_rule_id,
                        }
                    ],
                )
            )

    deduped = _dedup_by_precedence(selections)
    unmatched_files = sorted(set(normalized_changed) - matched_files)
    return {
        "selected": [s.__dict__ for s in deduped],
        "skipped_deferred": skipped_deferred,
        "changed_files": normalized_changed,
        "unmatched_files": unmatched_files,
        "matched_rules": sorted(matched_rules),
        "mode": "normal",
        "error_code": None,
        "before_missing_fallback": None,
    }
