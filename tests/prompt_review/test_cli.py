"""Tests for prompt review CLI subcommands."""

import json

from aria_esi.prompt_review.cli import main


def _write_tier_artifact(path, prompts, *, matcher=None, summary=None):
    """Write a minimal tier artifact JSON file."""
    data = {
        "schema_version": "v1",
        "prompts": prompts,
        "matcher": matcher or {},
        "summary": summary or {"total_prompts": len(prompts)},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def test_merge_tiers_happy_path_dedup_first_seen_wins(tmp_path):
    """3 tiers merge with first-seen-wins dedup on prompt_instance_id."""
    foundation = tmp_path / "foundation" / "combined.json"
    deep_dive = tmp_path / "deep-dive" / "combined.json"
    gate = tmp_path / "gate" / "combined.json"
    output = tmp_path / "output" / "combined.json"

    shared_prompt = {"prompt_instance_id": "shared-1", "tier": "foundation", "data": "from_foundation"}
    _write_tier_artifact(foundation, [
        shared_prompt,
        {"prompt_instance_id": "f-only", "tier": "foundation"},
    ])
    _write_tier_artifact(deep_dive, [
        {"prompt_instance_id": "shared-1", "tier": "deep_dive", "data": "from_deep_dive"},
        {"prompt_instance_id": "dd-only", "tier": "deep_dive"},
    ])
    _write_tier_artifact(gate, [
        {"prompt_instance_id": "g-only", "tier": "gate"},
    ])

    rc = main([
        "merge-tiers",
        "--foundation", str(foundation),
        "--deep-dive", str(deep_dive),
        "--gate", str(gate),
        "--output", str(output),
    ])

    assert rc == 0
    result = json.loads(output.read_text())
    ids = [p["prompt_instance_id"] for p in result["prompts"]]
    assert ids == ["shared-1", "f-only", "dd-only", "g-only"]
    # First-seen wins: shared-1 should have foundation data
    shared = next(p for p in result["prompts"] if p["prompt_instance_id"] == "shared-1")
    assert shared["data"] == "from_foundation"


def test_merge_tiers_missing_file_returns_exit_1(tmp_path):
    """Missing tier file returns exit 1."""
    foundation = tmp_path / "foundation" / "combined.json"
    deep_dive = tmp_path / "deep-dive" / "combined.json"
    gate = tmp_path / "gate" / "combined.json"
    output = tmp_path / "output" / "combined.json"

    _write_tier_artifact(foundation, [{"prompt_instance_id": "f-1", "tier": "foundation"}])
    _write_tier_artifact(gate, [{"prompt_instance_id": "g-1", "tier": "gate"}])
    # deep-dive file intentionally missing

    rc = main([
        "merge-tiers",
        "--foundation", str(foundation),
        "--deep-dive", str(deep_dive),
        "--gate", str(gate),
        "--output", str(output),
    ])

    assert rc == 1


def test_merge_tiers_summary_total_prompts_updated(tmp_path):
    """summary.total_prompts reflects the merged prompt count."""
    foundation = tmp_path / "foundation" / "combined.json"
    deep_dive = tmp_path / "deep-dive" / "combined.json"
    gate = tmp_path / "gate" / "combined.json"
    output = tmp_path / "output" / "combined.json"

    _write_tier_artifact(foundation, [
        {"prompt_instance_id": "f-1", "tier": "foundation"},
    ], summary={"total_prompts": 1})
    _write_tier_artifact(deep_dive, [
        {"prompt_instance_id": "dd-1", "tier": "deep_dive"},
    ])
    _write_tier_artifact(gate, [
        {"prompt_instance_id": "g-1", "tier": "gate"},
    ])

    rc = main([
        "merge-tiers",
        "--foundation", str(foundation),
        "--deep-dive", str(deep_dive),
        "--gate", str(gate),
        "--output", str(output),
    ])

    assert rc == 0
    result = json.loads(output.read_text())
    assert result["summary"]["total_prompts"] == 3
