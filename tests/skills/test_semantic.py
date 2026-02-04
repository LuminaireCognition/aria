"""
Layer 3: Semantic Validation Tests using G-Eval.

Evaluates response quality for natural language outputs using LLM-as-judge.
These tests verify factual accuracy, completeness, and persona consistency.

Run with: uv run pytest tests/skills/test_semantic.py -m semantic
Requires:
  - ANTHROPIC_API_KEY environment variable
  - deepeval package: uv pip install deepeval

Note: These tests are slow and incur API costs (~$0.10/test with Claude Haiku).
They are intended for weekly CI runs, not every PR.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

# Mark all tests in this module as semantic (slow, requires API)
pytestmark = [pytest.mark.semantic, pytest.mark.slow]

# =============================================================================
# Constants
# =============================================================================

EVALS_DIR = Path(__file__).parent / "evals"
GROUND_TRUTH_DIR = Path(__file__).parent / "ground_truth"


# =============================================================================
# G-Eval Configuration Loader
# =============================================================================


def load_eval_config(skill_name: str) -> dict[str, Any]:
    """
    Load G-Eval configuration for a skill.

    Args:
        skill_name: Name of the skill (e.g., "mission-brief")

    Returns:
        Eval configuration dictionary

    Raises:
        FileNotFoundError: If eval config doesn't exist
    """
    eval_path = EVALS_DIR / f"{skill_name.replace('-', '_')}.eval.yaml"
    if not eval_path.exists():
        raise FileNotFoundError(f"Eval config not found: {eval_path}")

    with open(eval_path) as f:
        return yaml.safe_load(f)


def load_ground_truth(category: str, name: str) -> dict[str, Any]:
    """
    Load ground truth data for semantic validation.

    Args:
        category: Category of ground truth (missions, fits, routes)
        name: Ground truth identifier (e.g., "the_blockade_l4")

    Returns:
        Ground truth data structure

    Raises:
        FileNotFoundError: If ground truth file doesn't exist
    """
    path = GROUND_TRUTH_DIR / category / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Ground truth not found: {path}")

    with open(path) as f:
        return json.load(f)


def get_active_persona() -> str:
    """
    Get the currently active persona profile for persona consistency checks.

    Reads from the active pilot's profile to extract persona context.

    Returns:
        Persona description string
    """
    import json

    # Read config to get active pilot
    config_path = Path("userdata/config.json")
    if not config_path.exists():
        return "Default ARIA assistant (rp_level=off)"

    try:
        with open(config_path) as f:
            config = json.load(f)

        active_pilot = config.get("active_pilot")
        if not active_pilot:
            return "Default ARIA assistant (rp_level=off)"

        # Read registry to get directory
        registry_path = Path("userdata/pilots/_registry.json")
        if not registry_path.exists():
            return "Default ARIA assistant (rp_level=off)"

        with open(registry_path) as f:
            registry = json.load(f)

        pilot_info = registry.get("pilots", {}).get(str(active_pilot))
        if not pilot_info:
            return "Default ARIA assistant (rp_level=off)"

        directory = pilot_info.get("directory")
        if not directory:
            return "Default ARIA assistant (rp_level=off)"

        # Read profile.md to extract persona_context
        profile_path = Path("userdata/pilots") / directory / "profile.md"
        if not profile_path.exists():
            return "Default ARIA assistant (rp_level=off)"

        with open(profile_path) as f:
            profile_content = f.read()

        # Extract rp_level and persona from profile
        rp_level = "off"
        persona = "aria"

        for line in profile_content.split("\n"):
            if line.startswith("rp_level:"):
                rp_level = line.split(":", 1)[1].strip()
            elif line.startswith("persona:"):
                persona = line.split(":", 1)[1].strip()

        return f"Persona: {persona} (rp_level={rp_level})"

    except (json.JSONDecodeError, OSError, KeyError):
        return "Default ARIA assistant (rp_level=off)"


# =============================================================================
# G-Eval Execution
# =============================================================================


def _check_deepeval_available() -> bool:
    """Check if deepeval package is installed."""
    try:
        import deepeval  # noqa: F401

        return True
    except ImportError:
        return False


def _check_api_key_available() -> bool:
    """Check if ANTHROPIC_API_KEY is set."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def skip_if_missing_requirements():
    """Skip test if deepeval or API key is missing."""
    if not _check_deepeval_available():
        pytest.skip("deepeval package not installed - run 'uv pip install deepeval'")
    if not _check_api_key_available():
        pytest.skip("ANTHROPIC_API_KEY not set")


async def run_g_eval(
    response: str,
    eval_config: dict[str, Any],
    ground_truth: dict[str, Any] | None = None,
    persona_profile: str | None = None,
) -> dict[str, float]:
    """
    Run G-Eval on a response.

    Args:
        response: The response to evaluate
        eval_config: Evaluation configuration from YAML
        ground_truth: Optional ground truth data for factual checks
        persona_profile: Optional persona description for voice checks

    Returns:
        Dictionary of criterion_name -> score (1-5)
    """
    skip_if_missing_requirements()

    from deepeval import evaluate
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    criteria = eval_config.get("criteria", {})
    model = eval_config.get("model", "claude-3-haiku-20240307")

    # Build metrics
    metrics = []
    for name, criterion in criteria.items():
        prompt = criterion["prompt"]

        # Substitute template variables
        if ground_truth:
            prompt = prompt.replace("{ground_truth}", json.dumps(ground_truth, indent=2))
        if persona_profile:
            prompt = prompt.replace("{persona_profile}", persona_profile)
        prompt = prompt.replace("{response}", response)

        metrics.append(
            GEval(
                name=name,
                criteria=prompt,
                evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
                model=model,
            )
        )

    # Create test case
    test_case = LLMTestCase(input="Skill evaluation", actual_output=response)

    # Run evaluation
    results = evaluate([test_case], metrics)

    # Extract scores
    scores = {}
    for metric in metrics:
        # deepeval returns scores in results structure
        scores[metric.name] = results[0].metrics_data[metric.name].score

    return scores


def calculate_weighted_score(scores: dict[str, float], eval_config: dict[str, Any]) -> float:
    """
    Calculate weighted average score.

    Args:
        scores: Dictionary of criterion_name -> score
        eval_config: Evaluation configuration with weights

    Returns:
        Weighted average score
    """
    criteria = eval_config.get("criteria", {})
    total_weight = 0.0
    weighted_sum = 0.0

    for name, criterion in criteria.items():
        weight = criterion.get("weight", 1.0)
        score = scores.get(name, 3.0)  # Default to neutral
        weighted_sum += weight * score
        total_weight += weight

    return weighted_sum / total_weight if total_weight > 0 else 3.0


# =============================================================================
# Skill Invocation Stubs
# =============================================================================


async def invoke_skill(
    skill_name: str,
    args: dict[str, Any],
    mock_tools: dict[str, Any] | None = None,
) -> str:
    """
    Invoke a skill and return its response.

    Uses the Tier 2 API invoker from tests/skills/integration/invokers.py
    to execute skills with mock tool responses.

    Args:
        skill_name: Name of the skill to invoke (e.g., "mission-brief")
        args: Arguments to pass to the skill (e.g., {"mission": "The Blockade", "level": 4})
        mock_tools: Optional dict mapping tool_name to mock responses.
                    Keys can be "tool_name" or "tool_name_action" for action-specific mocks.

    Returns:
        Skill response text

    Raises:
        ImportError: If anthropic package is not installed
        ValueError: If ANTHROPIC_API_KEY is not set

    Example:
        response = await invoke_skill(
            "mission-brief",
            {"mission": "The Blockade", "level": 4},
            mock_tools={
                "sde_item_info": {"name": "Blood Raiders", "damage_profile": "EM/Thermal"},
            }
        )
    """
    from tests.skills.integration.invokers import invoke_via_api

    # Build skill args string from dict
    args_str = " ".join(f"--{k} {v}" for k, v in args.items())

    result = await invoke_via_api(
        skill_name=skill_name,
        skill_args=args_str,
        mock_tools=mock_tools,
    )

    return result["response"]


def load_skill_fixture_mocks(skill_name: str, fixture_name: str) -> dict[str, Any]:
    """
    Load mock tool responses from a fixture YAML file.

    Fixture files are stored at tests/skills/evals/fixtures/{skill_name}/{fixture_name}.yaml

    Args:
        skill_name: Name of the skill (e.g., "mission-brief")
        fixture_name: Name of the fixture (e.g., "the_blockade_l4")

    Returns:
        Dict mapping tool_name (or tool_name_action) to mock responses

    Raises:
        FileNotFoundError: If fixture file doesn't exist
    """
    fixture_path = EVALS_DIR / "fixtures" / skill_name.replace("-", "_") / f"{fixture_name}.yaml"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    with open(fixture_path) as f:
        fixture_data = yaml.safe_load(f)

    return fixture_data.get("mock_tools", {})


# =============================================================================
# Test Classes
# =============================================================================


class TestMissionBriefSemantic:
    """Semantic validation for /mission-brief skill."""

    @pytest.mark.asyncio
    async def test_mission_brief_factual_accuracy(self):
        """Evaluate mission brief factual accuracy via LLM-as-judge."""
        skip_if_missing_requirements()

        # Load configuration
        eval_config = load_eval_config("mission-brief")
        ground_truth = load_ground_truth("missions", "the_blockade_l4")

        # In real test, would invoke skill
        # response = await invoke_skill("mission-brief", {"mission": "The Blockade", "level": 4})

        # For now, use a placeholder that demonstrates the evaluation structure
        pytest.skip(
            "Full implementation requires skill invocation framework. "
            "See invoke_skill() for integration points."
        )

    @pytest.mark.asyncio
    async def test_mission_brief_completeness(self):
        """Evaluate mission brief completeness via LLM-as-judge."""
        skip_if_missing_requirements()
        pytest.skip("Pending skill invocation framework integration")

    @pytest.mark.asyncio
    async def test_mission_brief_with_sample_response(self):
        """
        Test G-Eval scoring with a sample response.

        This test verifies the G-Eval infrastructure works correctly
        using a pre-crafted sample response rather than invoking the skill.
        """
        skip_if_missing_requirements()

        eval_config = load_eval_config("mission-brief")
        ground_truth = load_ground_truth("missions", "the_blockade_l4")

        # Sample response for testing G-Eval infrastructure
        sample_response = """
        ## The Blockade (Level 4)

        **Faction:** Blood Raiders
        **Objective:** Destroy the pirate stargate

        ### Enemy Forces
        - Frigates: 5-8 Corpii Elite
        - Cruisers: 4-6 Corpum Elite
        - Battleships: 3-5 Corpus

        ### Damage Profile
        - **Tank:** EM/Thermal (Blood Raiders deal EM primary)
        - **Deal:** EM/Thermal (Blood Raiders are weakest to EM)

        ### Trigger Warning
        Destroying the stargate will trigger a reinforcement wave!
        Clear all initial spawns before engaging the stargate.

        ### Recommended Setup
        - Ship: Battleship or Marauder
        - Tank: EM/Thermal hardeners
        - Weapons: Lasers or EM missiles
        - Bring drones for frigate cleanup

        Fly safe, capsuleer.
        """

        # Run G-Eval
        scores = await run_g_eval(
            response=sample_response,
            eval_config=eval_config,
            ground_truth=ground_truth,
            persona_profile=get_active_persona(),
        )

        # Calculate weighted score
        weighted = calculate_weighted_score(scores, eval_config)
        threshold = eval_config.get("passing_threshold", 3.5)

        assert weighted >= threshold, (
            f"Quality score {weighted:.2f} below threshold {threshold}. "
            f"Scores: {scores}"
        )


class TestFittingSemantic:
    """Semantic validation for /fitting skill."""

    @pytest.mark.asyncio
    async def test_fitting_pve_recommendation_quality(self):
        """Evaluate PvE fit recommendation quality via LLM-as-judge."""
        skip_if_missing_requirements()
        pytest.skip("Pending skill invocation framework integration")


class TestExplorationSemantic:
    """Semantic validation for /exploration skill."""

    @pytest.mark.asyncio
    async def test_exploration_site_analysis_quality(self):
        """Evaluate exploration site analysis quality."""
        skip_if_missing_requirements()
        pytest.skip("Pending skill invocation framework integration")


# =============================================================================
# Infrastructure Tests
# =============================================================================


class TestSemanticInfrastructure:
    """Tests for the semantic evaluation infrastructure itself."""

    def test_load_eval_config(self):
        """Verify eval configs can be loaded."""
        config = load_eval_config("mission-brief")
        assert "criteria" in config
        assert "passing_threshold" in config

    def test_load_ground_truth(self):
        """Verify ground truth files can be loaded."""
        ground_truth = load_ground_truth("missions", "the_blockade_l4")
        assert "mission_name" in ground_truth
        assert "common_facts" in ground_truth

    def test_eval_config_has_weights(self):
        """Verify all criteria have weights defined."""
        config = load_eval_config("mission-brief")
        for name, criterion in config["criteria"].items():
            assert "weight" in criterion, f"Criterion '{name}' missing weight"
            assert 0 < criterion["weight"] <= 1, f"Criterion '{name}' has invalid weight"

    def test_weights_sum_approximately_one(self):
        """Verify weights sum to approximately 1.0."""
        config = load_eval_config("mission-brief")
        total_weight = sum(c["weight"] for c in config["criteria"].values())
        assert 0.99 <= total_weight <= 1.01, f"Weights sum to {total_weight}, should be ~1.0"
