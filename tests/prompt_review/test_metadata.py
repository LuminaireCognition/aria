"""Tests for prompt metadata validation."""

from datetime import datetime, timezone

from aria_esi.prompt_review.metadata import validate_prompt_metadata


def test_prompt_metadata_check_enforces_required_headers(tmp_path):
    """#21: Missing metadata headers are detected on v1 prompts."""
    prompts_dir = tmp_path / "prompts"
    _create_minimal_prompt_tree(prompts_dir)

    # All prompts have no metadata — all should have issues
    result = validate_prompt_metadata(
        prompts_dir,
        now_utc=datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc),
    )
    # Before cutover: warnings only, so ok should be True
    assert result.ok is True
    assert result.prompts_checked == 14
    # But there should be issues (warnings)
    assert len(result.issues) > 0
    assert all(not issue.is_error for issue in result.issues)

    # After cutover: hard failure
    result_after = validate_prompt_metadata(
        prompts_dir,
        now_utc=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
    )
    assert result_after.ok is False
    assert any(issue.is_error for issue in result_after.issues)


def test_prompt_metadata_schema_validation_strict(tmp_path):
    """#42: Metadata field grammar is validated strictly."""
    prompts_dir = tmp_path / "prompts"
    _create_minimal_prompt_tree(prompts_dir)

    # Add metadata with invalid owner format to one prompt
    meta_prompt = prompts_dir / "meta" / "scoring_rubric.md"
    meta_prompt.write_text(
        "<!-- owner: not-a-valid-owner -->\n"
        "<!-- last_reviewed: not-a-date -->\n"
        "<!-- depends_on: [] -->\n"
        "<!-- adjacent_prompts: [] -->\n"
        "# Scoring Rubric\n"
    )

    # After cutover, invalid formats should fail
    result = validate_prompt_metadata(
        prompts_dir,
        now_utc=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
    )
    assert result.ok is False
    invalid_issues = [i for i in result.issues if i.code == "invalid_metadata_field"]
    # Should have invalid owner and invalid last_reviewed for this prompt
    scoring_issues = [i for i in invalid_issues if "scoring_rubric" in i.prompt_path]
    assert len(scoring_issues) >= 2


def _create_minimal_prompt_tree(prompts_dir):
    """Create minimal prompt files for all 14 v1 prompts."""
    from aria_esi.prompt_review.metadata import V1_PROMPT_PATHS

    for prompt_path in V1_PROMPT_PATHS:
        full_path = prompts_dir / prompt_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(f"# {prompt_path}\n\nPrompt content.\n")
