from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .aggregate import aggregate_combined_results
from .matcher import select_prompts
from .metadata import validate_prompt_metadata
from .orchestrator import run_orchestrator_check
from .waivers import validate_high_waivers


def _parse_now(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _cmd_match(args: argparse.Namespace) -> int:
    changed_files = []
    if args.changed_files:
        changed_files = [
            line.strip()
            for line in Path(args.changed_files).read_text().splitlines()
            if line.strip()
        ]

    proposal_paths = None
    if args.proposal_paths:
        proposal_paths = [
            line.strip()
            for line in Path(args.proposal_paths).read_text().splitlines()
            if line.strip()
        ]

    selected = select_prompts(
        config_path=args.config,
        event=args.event,
        changed_files=changed_files,
        proposal_paths=proposal_paths,
        postmerge_applicable=args.postmerge_applicable,
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(selected, indent=2) + "\n", encoding="utf-8")
    return 0


def _cmd_aggregate(args: argparse.Namespace) -> int:
    result = aggregate_combined_results(args.combined, now_utc=_parse_now(args.now))
    payload = {
        "gate_decision": result.gate_decision,
        "unresolved_high_count": result.unresolved_high_count,
        "requires_high_waiver_check": result.requires_high_waiver_check,
        "issues": [issue.__dict__ for issue in result.issues],
        "normalized": result.normalized,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0 if result.gate_decision == "pass" else 1


def _cmd_waiver_check(args: argparse.Namespace) -> int:
    result = validate_high_waivers(
        combined_json_path=args.combined,
        waiver_yaml_path=args.waivers,
        codeowners_path=args.codeowners,
        now_utc=_parse_now(args.now),
    )
    payload = {"ok": result.ok, "issues": [issue.__dict__ for issue in result.issues]}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0 if result.ok else 1


def _cmd_orchestrator_check(args: argparse.Namespace) -> int:
    combined_results: dict = {"foundation": [], "deep_dive": [], "gate": [], "matcher": {}}
    failed_artifacts: list[str] = []
    for label, path in [
        ("foundation", args.foundation_results),
        ("deep_dive", args.deep_dive_results),
        ("gate", args.gate_results),
    ]:
        if path:
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                combined_results[label] = data.get("prompts", [])
                if label == "foundation":
                    combined_results["matcher"] = data.get("matcher", {})
            except (FileNotFoundError, json.JSONDecodeError) as exc:
                print(
                    f"WARNING: Failed to load {label} artifact from {path}: {exc}",
                    file=sys.stderr,
                )
                failed_artifacts.append(label)

    result = run_orchestrator_check(combined_results)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if "foundation" in failed_artifacts:
        return 1
    return 0


def _cmd_metadata_check(args: argparse.Namespace) -> int:
    result = validate_prompt_metadata(
        args.prompts_dir,
        now_utc=_parse_now(args.now),
    )
    payload = {
        "ok": result.ok,
        "prompts_checked": result.prompts_checked,
        "issues": [
            {
                "prompt_path": issue.prompt_path,
                "field": issue.field,
                "code": issue.code,
                "message": issue.message,
                "is_error": issue.is_error,
            }
            for issue in result.issues
        ],
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prompt-review")
    sub = parser.add_subparsers(dest="cmd", required=True)

    match = sub.add_parser("match")
    match.add_argument("--config", required=True)
    match.add_argument("--event", required=True)
    match.add_argument("--changed-files", required=True)
    match.add_argument("--proposal-paths")
    match.add_argument("--postmerge-applicable", action="store_true")
    match.add_argument("--output", required=True)
    match.set_defaults(func=_cmd_match)

    aggregate = sub.add_parser("aggregate")
    aggregate.add_argument("--combined", required=True)
    aggregate.add_argument("--output", required=True)
    aggregate.add_argument("--now")
    aggregate.set_defaults(func=_cmd_aggregate)

    waiver = sub.add_parser("waiver-check")
    waiver.add_argument("--combined", required=True)
    waiver.add_argument("--waivers", required=True)
    waiver.add_argument("--codeowners", required=True)
    waiver.add_argument("--output", required=True)
    waiver.add_argument("--now")
    waiver.set_defaults(func=_cmd_waiver_check)

    orch = sub.add_parser("orchestrator-check")
    orch.add_argument("--foundation-results")
    orch.add_argument("--deep-dive-results")
    orch.add_argument("--gate-results")
    orch.add_argument("--output", required=True)
    orch.set_defaults(func=_cmd_orchestrator_check)

    meta = sub.add_parser("metadata-check")
    meta.add_argument("--prompts-dir", required=True)
    meta.add_argument("--output", required=True)
    meta.add_argument("--now")
    meta.set_defaults(func=_cmd_metadata_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
