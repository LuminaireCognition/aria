"""Tests for prompt metadata validation."""

from datetime import datetime, timezone

from aria_esi.prompt_review.metadata import (
    V1_PROMPT_PATHS,
    _parse_list_field,
    _parse_metadata_block,
    validate_prompt_metadata,
)


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


def test_valid_metadata_passes_cleanly(tmp_path):
    """All 14 prompts with valid metadata produce zero issues."""
    prompts_dir = tmp_path / "prompts"
    _create_prompt_tree_with_valid_metadata(prompts_dir)

    result = validate_prompt_metadata(
        prompts_dir,
        now_utc=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
    )
    assert result.ok is True
    assert result.prompts_checked == 14
    assert len(result.issues) == 0


def test_depends_on_unknown_prompt_id_flagged(tmp_path):
    """_validate_depends_on rejects unknown prompt IDs."""
    prompts_dir = tmp_path / "prompts"
    _create_prompt_tree_with_valid_metadata(prompts_dir)

    # Overwrite one prompt with a bogus depends_on
    bad_prompt = prompts_dir / "meta" / "scoring_rubric.md"
    bad_prompt.write_text(
        "<!-- owner: @anthropic/aria -->\n"
        "<!-- last_reviewed: 2026-02-10T00:00:00Z -->\n"
        "<!-- depends_on: [nonexistent.prompt_id] -->\n"
        "<!-- adjacent_prompts: [] -->\n"
        "# Scoring Rubric\n"
    )

    result = validate_prompt_metadata(
        prompts_dir,
        now_utc=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
    )
    assert result.ok is False
    depends_issues = [
        i for i in result.issues
        if i.field == "depends_on" and "unknown prompt_id" in i.message
    ]
    assert len(depends_issues) == 1


def test_adjacent_prompts_unknown_path_flagged(tmp_path):
    """_validate_adjacent_prompts rejects unknown paths."""
    prompts_dir = tmp_path / "prompts"
    _create_prompt_tree_with_valid_metadata(prompts_dir)

    bad_prompt = prompts_dir / "meta" / "scoring_rubric.md"
    bad_prompt.write_text(
        "<!-- owner: @anthropic/aria -->\n"
        "<!-- last_reviewed: 2026-02-10T00:00:00Z -->\n"
        "<!-- depends_on: [] -->\n"
        "<!-- adjacent_prompts: [nonexistent/path.md] -->\n"
        "# Scoring Rubric\n"
    )

    result = validate_prompt_metadata(
        prompts_dir,
        now_utc=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
    )
    assert result.ok is False
    adj_issues = [
        i for i in result.issues
        if i.field == "adjacent_prompts" and "unknown path" in i.message
    ]
    assert len(adj_issues) == 1


def test_parse_list_field_edge_cases():
    """_parse_list_field handles empty brackets, single item, quoted items, bare value."""
    assert _parse_list_field("[]") == []
    assert _parse_list_field("[foo]") == ["foo"]
    assert _parse_list_field('[foo, "bar", \'baz\']') == ["foo", "bar", "baz"]
    assert _parse_list_field("bare_value") == ["bare_value"]
    assert _parse_list_field("  [  spaced  ]  ") == ["spaced"]


def test_yaml_frontmatter_metadata_is_parsed():
    """YAML --- frontmatter parsing path extracts metadata."""
    content = (
        "---\n"
        "owner: @anthropic/aria\n"
        "last_reviewed: 2026-02-10T00:00:00Z\n"
        "depends_on: []\n"
        "adjacent_prompts: []\n"
        "---\n"
        "# Prompt\n"
    )
    metadata = _parse_metadata_block(content)
    assert metadata["owner"] == "@anthropic/aria"
    assert metadata["last_reviewed"] == "2026-02-10T00:00:00Z"
    assert metadata["depends_on"] == "[]"
    assert metadata["adjacent_prompts"] == "[]"


def test_hyphenated_field_names_are_parsed():
    """Hyphenated field names in HTML comments are parsed correctly."""
    content = (
        "<!-- last-reviewed: 2026-02-10T00:00:00Z -->\n"
        "<!-- my-custom-field: some_value -->\n"
    )
    metadata = _parse_metadata_block(content)
    assert "last-reviewed" in metadata
    assert metadata["last-reviewed"] == "2026-02-10T00:00:00Z"
    assert metadata["my-custom-field"] == "some_value"


def _create_minimal_prompt_tree(prompts_dir):
    """Create minimal prompt files for all 14 v1 prompts (no metadata)."""
    for prompt_path in V1_PROMPT_PATHS:
        full_path = prompts_dir / prompt_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(f"# {prompt_path}\n\nPrompt content.\n")


def _create_prompt_tree_with_valid_metadata(prompts_dir):
    """Create all 14 v1 prompts with valid metadata headers."""
    for prompt_path in V1_PROMPT_PATHS:
        full_path = prompts_dir / prompt_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(
            "<!-- owner: @anthropic/aria -->\n"
            "<!-- last_reviewed: 2026-02-10T00:00:00Z -->\n"
            "<!-- depends_on: [] -->\n"
            "<!-- adjacent_prompts: [] -->\n"
            f"# {prompt_path}\n\nPrompt content.\n"
        )
