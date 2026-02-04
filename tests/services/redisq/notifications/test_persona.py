"""
Tests for persona voice loader.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import mock_open, patch

from aria_esi.services.redisq.notifications.persona import (
    ARIA_VOICE,
    DEFAULT_VOICE,
    PARIA_VOICE,
    VOICE_SUMMARIES,
    PersonaLoader,
    PersonaVoiceSummary,
    get_persona_loader,
    reset_persona_loader,
)


class TestPersonaVoiceSummary:
    """Tests for PersonaVoiceSummary dataclass."""

    def test_to_prompt_context(self):
        """Test prompt context generation."""
        voice = PersonaVoiceSummary(
            name="TEST",
            tone="Direct and tactical",
            address_form="Commander",
            example_phrases=["Test phrase 1", "Test phrase 2"],
            avoid=["Avoid 1", "Avoid 2"],
        )

        context = voice.to_prompt_context()

        assert "PERSONA: TEST" in context
        assert "TONE: Direct and tactical" in context
        assert 'ADDRESS: Use "Commander"' in context
        assert "Test phrase 1" in context
        assert "AVOID:" in context
        assert "Avoid 1" in context

    def test_to_prompt_context_limits_examples(self):
        """Test that only first 3 examples are included."""
        voice = PersonaVoiceSummary(
            name="TEST",
            tone="Test",
            address_form="Test",
            example_phrases=["1", "2", "3", "4", "5"],
            avoid=[],
        )

        context = voice.to_prompt_context()

        # Should only have 3 examples
        assert '"1"' in context
        assert '"2"' in context
        assert '"3"' in context
        assert '"4"' not in context
        assert '"5"' not in context

    def test_to_dict(self):
        """Test serialization to dict."""
        voice = PersonaVoiceSummary(
            name="TEST",
            tone="Direct",
            address_form="Commander",
            example_phrases=["Phrase 1"],
            avoid=["Avoid 1"],
        )

        result = voice.to_dict()

        assert result["name"] == "TEST"
        assert result["tone"] == "Direct"
        assert result["address_form"] == "Commander"
        assert result["example_phrases"] == ["Phrase 1"]
        assert result["avoid"] == ["Avoid 1"]


class TestPredefinedVoices:
    """Tests for pre-defined voice summaries."""

    def test_aria_voice_properties(self):
        """Test ARIA voice summary properties."""
        assert ARIA_VOICE.name == "ARIA"
        assert ARIA_VOICE.address_form == "Capsuleer"
        assert "Gallente" in ARIA_VOICE.tone
        assert len(ARIA_VOICE.example_phrases) > 0
        assert len(ARIA_VOICE.avoid) > 0

    def test_paria_voice_properties(self):
        """Test PARIA voice summary properties."""
        assert PARIA_VOICE.name == "PARIA"
        assert PARIA_VOICE.address_form == "Captain"
        assert "Direct" in PARIA_VOICE.tone
        assert len(PARIA_VOICE.example_phrases) > 0
        assert len(PARIA_VOICE.avoid) > 0

    def test_default_voice_properties(self):
        """Test default voice summary properties."""
        assert DEFAULT_VOICE.name == "ARIA"
        assert DEFAULT_VOICE.address_form == "pilot"
        assert "tactical" in DEFAULT_VOICE.tone.lower()

    def test_voice_summaries_registry(self):
        """Test voice summaries are properly registered."""
        assert "aria-mk4" in VOICE_SUMMARIES
        assert "aria" in VOICE_SUMMARIES
        assert "paria" in VOICE_SUMMARIES
        assert "default" in VOICE_SUMMARIES

        # Aliases should point to same objects
        assert VOICE_SUMMARIES["aria"] is VOICE_SUMMARIES["aria-mk4"]


class TestPersonaLoader:
    """Tests for PersonaLoader class."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_persona_loader()

    def test_get_default_voice_no_pilot(self):
        """Test getting default voice when no pilot configured."""
        loader = PersonaLoader()

        # Mock no config files exist
        with patch.object(Path, "exists", return_value=False):
            voice = loader.get_voice_summary()

        assert voice == DEFAULT_VOICE

    def test_get_persona_name(self):
        """Test getting persona display name."""
        loader = PersonaLoader()

        with patch.object(Path, "exists", return_value=False):
            name = loader.get_persona_name()

        assert name == "ARIA"

    def test_detect_aria_persona_from_profile(self):
        """Test detecting ARIA persona from profile."""
        loader = PersonaLoader(pilot_directory="test_pilot")

        profile_content = """
# Pilot Profile

persona_context:
  branch: empire
  persona: aria-mk4
  rp_level: on
"""

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=profile_content),
        ):
            voice = loader.get_voice_summary()

        assert voice == ARIA_VOICE

    def test_detect_paria_persona_from_profile(self):
        """Test detecting PARIA persona from profile."""
        loader = PersonaLoader(pilot_directory="test_pilot")

        profile_content = """
# Pilot Profile

persona_context:
  branch: pirate
  persona: paria
  rp_level: full
"""

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=profile_content),
        ):
            voice = loader.get_voice_summary()

        assert voice == PARIA_VOICE

    def test_caching(self):
        """Test that persona detection is cached."""
        loader = PersonaLoader()

        with patch.object(Path, "exists", return_value=False):
            voice1 = loader.get_voice_summary()
            voice2 = loader.get_voice_summary()

        assert voice1 is voice2

    def test_clear_cache(self):
        """Test cache clearing."""
        loader = PersonaLoader()

        with patch.object(Path, "exists", return_value=False):
            _ = loader.get_voice_summary()

        loader.clear_cache()

        assert loader._cached_persona is None
        assert loader._cached_voice is None

    def test_load_from_config_json(self):
        """Test loading pilot directory from config.json."""
        loader = PersonaLoader()

        config_content = json.dumps({"active_pilot": "123456"})
        # SEC-001: Directory name must be in format "{id}_{name}" where id is numeric
        registry_content = json.dumps(
            {"pilots": [{"character_id": 123456, "directory": "123456_test_pilot"}]}
        )
        profile_content = """
persona_context:
  persona: paria
"""

        def mock_exists(self):
            return True

        def mock_open_files(path, *args, **kwargs):
            path_str = str(path)
            if "config.json" in path_str:
                return mock_open(read_data=config_content)()
            elif "_registry.json" in path_str:
                return mock_open(read_data=registry_content)()
            else:
                return mock_open(read_data=profile_content)()

        with (
            patch.object(Path, "exists", mock_exists),
            patch("builtins.open", mock_open_files),
            patch.object(Path, "read_text", return_value=profile_content),
        ):
            voice = loader.get_voice_summary()

        assert voice == PARIA_VOICE

    def test_fallback_to_default_on_invalid_profile(self):
        """Test fallback to default when profile is invalid."""
        loader = PersonaLoader(pilot_directory="test_pilot")

        # Profile without persona_context
        profile_content = """
# Pilot Profile
character_name: Test Pilot
"""

        with (
            patch.object(Path, "exists", return_value=True),
            patch("builtins.open", mock_open(read_data=profile_content)),
        ):
            voice = loader.get_voice_summary()

        assert voice == DEFAULT_VOICE


class TestPersonaLoaderSingleton:
    """Tests for persona loader singleton."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_persona_loader()

    def test_get_persona_loader_creates_singleton(self):
        """Test that get_persona_loader creates singleton."""
        loader1 = get_persona_loader()
        loader2 = get_persona_loader()

        assert loader1 is loader2

    def test_reset_persona_loader(self):
        """Test resetting the singleton."""
        loader1 = get_persona_loader()
        reset_persona_loader()
        loader2 = get_persona_loader()

        assert loader1 is not loader2

    def test_get_persona_loader_with_directory(self):
        """Test creating loader with pilot directory."""
        loader = get_persona_loader(pilot_directory="test_dir")

        assert loader._pilot_directory == "test_dir"
