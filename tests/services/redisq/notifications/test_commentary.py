"""
Tests for LLM commentary generation.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.services.redisq.models import ProcessedKill
from aria_esi.services.redisq.notifications.commentary import (
    COST_PER_1K_INPUT_TOKENS,
    COST_PER_1K_OUTPUT_TOKENS,
    PATTERN_STRESS_MAP,
    CommentaryGenerator,
    CommentaryMetrics,
    CommentaryStyle,
    StressLevel,
    create_commentary_generator,
    extract_protected_tokens,
    get_stress_level,
    validate_preserved_tokens,
)
from aria_esi.services.redisq.notifications.patterns import DetectedPattern, PatternContext
from aria_esi.services.redisq.notifications.persona import PersonaLoader, PersonaVoiceSummary
from aria_esi.services.redisq.notifications.prompts import (
    build_system_prompt,
)
from aria_esi.services.redisq.notifications.types import PatternSeverity


class TestCommentaryMetrics:
    """Tests for CommentaryMetrics class."""

    def test_initial_state(self):
        """Test initial metrics state."""
        metrics = CommentaryMetrics()

        assert metrics.generated_count == 0
        assert metrics.timeout_count == 0
        assert metrics.error_count == 0
        assert metrics.no_commentary_count == 0
        assert metrics.daily_cost_estimate == 0.0

    def test_record_generation(self):
        """Test recording a successful generation."""
        metrics = CommentaryMetrics()
        metrics.record_generation(500, 50)

        assert metrics.generated_count == 1
        assert metrics.total_input_tokens == 500
        assert metrics.total_output_tokens == 50

    def test_record_timeout(self):
        """Test recording a timeout."""
        metrics = CommentaryMetrics()
        metrics.record_timeout()

        assert metrics.timeout_count == 1

    def test_record_error(self):
        """Test recording an error."""
        metrics = CommentaryMetrics()
        metrics.record_error()

        assert metrics.error_count == 1

    def test_record_no_commentary(self):
        """Test recording LLM declining."""
        metrics = CommentaryMetrics()
        metrics.record_no_commentary()

        assert metrics.no_commentary_count == 1

    def test_daily_cost_estimate(self):
        """Test daily cost estimation."""
        metrics = CommentaryMetrics()
        metrics.record_generation(1000, 100)

        expected_cost = (1000 / 1000) * COST_PER_1K_INPUT_TOKENS + (100 / 1000) * COST_PER_1K_OUTPUT_TOKENS
        assert abs(metrics.daily_cost_estimate - expected_cost) < 0.0001

    def test_check_daily_limit_within(self):
        """Test checking daily limit when within budget."""
        metrics = CommentaryMetrics()
        metrics.record_generation(500, 50)

        assert metrics.check_daily_limit(1.0) is True

    def test_check_daily_limit_exceeded(self):
        """Test checking daily limit when exceeded."""
        from datetime import date

        metrics = CommentaryMetrics()
        # Set the daily date to prevent reset
        metrics._daily_date = date.today()

        # Simulate many generations
        for _ in range(10000):
            metrics.total_input_tokens += 500
            metrics.total_output_tokens += 50

        assert metrics.check_daily_limit(0.01) is False

    def test_to_dict(self):
        """Test serialization to dict."""
        metrics = CommentaryMetrics()
        metrics.record_generation(500, 50)
        metrics.record_timeout()

        result = metrics.to_dict()

        assert result["generated_count"] == 1
        assert result["timeout_count"] == 1
        assert result["total_input_tokens"] == 500
        assert result["total_output_tokens"] == 50
        assert "daily_cost_estimate_usd" in result


class TestCommentaryGenerator:
    """Tests for CommentaryGenerator class."""

    @pytest.fixture
    def sample_kill(self):
        """Create sample ProcessedKill."""
        return ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now() - timedelta(minutes=2),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=99000001,
            attacker_count=8,
            attacker_corps=[98000002],
            attacker_alliances=[99000002],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )

    @pytest.fixture
    def mock_persona_loader(self):
        """Create mock PersonaLoader."""
        from aria_esi.services.redisq.notifications.persona import PersonaVoiceSummary

        loader = MagicMock(spec=PersonaLoader)
        loader.get_voice_summary.return_value = PersonaVoiceSummary(
            name="TEST",
            tone="Direct and tactical",
            address_form="Captain",
            example_phrases=["Test phrase"],
            avoid=["Avoid this"],
        )
        loader.get_persona_name.return_value = "TEST"
        return loader

    @pytest.fixture
    def pattern_context(self, sample_kill):
        """Create sample PatternContext."""
        return PatternContext(
            kill=sample_kill,
            patterns=[
                DetectedPattern(
                    pattern_type="gank_rotation",
                    description="Gank rotation detected",
                    weight=0.5,
                ),
            ],
            same_attacker_kills_1h=3,
            same_system_kills_1h=5,
        )

    def test_not_configured_without_api_key(self, mock_persona_loader):
        """Test is_configured is False without API key."""
        # Mock settings to return no API key (simulates missing .env)
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = None

        with patch(
            "aria_esi.core.config.get_settings",
            return_value=mock_settings,
        ):
            generator = CommentaryGenerator(
                persona_loader=mock_persona_loader,
                api_key=None,
            )

            assert generator.is_configured is False

    def test_is_configured_with_api_key(self, mock_persona_loader):
        """Test is_configured is True with API key."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
        )

        assert generator.is_configured is True

    @pytest.mark.asyncio
    async def test_generate_commentary_success(self, mock_persona_loader, pattern_context):
        """Test successful commentary generation."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
        )

        # Mock the Anthropic client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Third gank in this system. They're running a rotation.")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=30)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch.object(generator, "_get_client", return_value=mock_client):
            result = await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
                timeout_ms=3000,
            )

        assert result == "Third gank in this system. They're running a rotation."
        assert generator.get_metrics().generated_count == 1

    @pytest.mark.asyncio
    async def test_generate_commentary_no_commentary_signal(self, mock_persona_loader, pattern_context):
        """Test handling NO_COMMENTARY signal."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="NO_COMMENTARY")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=10)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch.object(generator, "_get_client", return_value=mock_client):
            result = await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
            )

        assert result is None
        assert generator.get_metrics().no_commentary_count == 1

    @pytest.mark.asyncio
    async def test_generate_commentary_timeout(self, mock_persona_loader, pattern_context):
        """Test handling timeout."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
        )

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(10)
            return MagicMock()

        mock_client = AsyncMock()
        mock_client.messages.create = slow_response

        with patch.object(generator, "_get_client", return_value=mock_client):
            result = await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
                timeout_ms=100,  # Very short timeout
            )

        assert result is None
        assert generator.get_metrics().timeout_count == 1

    @pytest.mark.asyncio
    async def test_generate_commentary_error(self, mock_persona_loader, pattern_context):
        """Test handling errors."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
        )

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API Error"))

        with patch.object(generator, "_get_client", return_value=mock_client):
            result = await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
            )

        assert result is None
        assert generator.get_metrics().error_count == 1

    @pytest.mark.asyncio
    async def test_generate_commentary_cost_limit_exceeded(self, mock_persona_loader, pattern_context):
        """Test that generation is skipped when cost limit exceeded."""
        from datetime import date

        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
            cost_limit_daily_usd=0.001,  # Very low limit
        )

        # Set daily date to prevent reset and inflate token usage
        generator._metrics._daily_date = date.today()
        generator._metrics.total_input_tokens = 100000
        generator._metrics.total_output_tokens = 10000

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock()

        with patch.object(generator, "_get_client", return_value=mock_client):
            result = await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
            )

        assert result is None
        # Should not have called the API
        mock_client.messages.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_commentary_empty_response(self, mock_persona_loader, pattern_context):
        """Test handling empty response."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=0)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch.object(generator, "_get_client", return_value=mock_client):
            result = await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
            )

        assert result is None
        assert generator.get_metrics().no_commentary_count == 1


class TestCreateCommentaryGenerator:
    """Tests for create_commentary_generator factory."""

    def test_create_with_defaults(self):
        """Test creation with default config."""
        mock_loader = MagicMock(spec=PersonaLoader)

        generator = create_commentary_generator(mock_loader)

        assert generator._model == "claude-sonnet-4-5-20241022"
        assert generator._max_tokens == 100
        assert generator._default_timeout_ms == 3000
        assert generator._cost_limit_daily_usd == 1.0

    def test_create_with_custom_config(self):
        """Test creation with custom config."""
        mock_loader = MagicMock(spec=PersonaLoader)
        config = {
            "model": "claude-3-opus-20240229",
            "max_tokens": 200,
            "timeout_ms": 5000,
            "cost_limit_daily_usd": 2.0,
            "api_key": "custom-key",
        }

        generator = create_commentary_generator(mock_loader, config)

        assert generator._model == "claude-3-opus-20240229"
        assert generator._max_tokens == 200
        assert generator._default_timeout_ms == 5000
        assert generator._cost_limit_daily_usd == 2.0
        assert generator._api_key == "custom-key"


class TestPrompts:
    """Tests for prompt building."""

    def test_build_system_prompt(self):
        """Test system prompt building."""
        from aria_esi.services.redisq.notifications.persona import PersonaVoiceSummary
        from aria_esi.services.redisq.notifications.prompts import build_system_prompt

        voice = PersonaVoiceSummary(
            name="TEST",
            tone="Direct",
            address_form="Captain",
            example_phrases=["Phrase 1"],
            avoid=["Avoid 1"],
        )

        prompt = build_system_prompt(voice)

        assert "tactical commentary" in prompt.lower()
        assert "tactical insight" in prompt.lower()
        assert "NO_COMMENTARY" in prompt
        assert "PERSONA: TEST" in prompt

    def test_build_user_prompt(self):
        """Test user prompt building."""
        from aria_esi.services.redisq.notifications.prompts import build_user_prompt

        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )

        context = PatternContext(
            kill=kill,
            patterns=[
                DetectedPattern(
                    pattern_type="repeat_attacker",
                    description="Same attackers with 4 kills",
                    weight=0.4,
                ),
            ],
            same_attacker_kills_1h=3,
            same_system_kills_1h=5,
        )

        prompt = build_user_prompt("Test notification text", context)

        assert "Test notification text" in prompt
        assert "repeat_attacker" in prompt
        assert "Same attackers: 3" in prompt
        assert "Same system: 5" in prompt

    def test_build_user_prompt_no_patterns(self):
        """Test user prompt with no patterns."""
        from aria_esi.services.redisq.notifications.prompts import build_user_prompt

        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )

        context = PatternContext(
            kill=kill,
            patterns=[],
        )

        prompt = build_user_prompt("Test notification", context)

        assert "None detected" in prompt


class TestCommentaryStyle:
    """Tests for style layer enums."""

    def test_style_enum_values(self):
        """Test CommentaryStyle enum values."""
        assert CommentaryStyle.CONVERSATIONAL.value == "conversational"
        assert CommentaryStyle.RADIO.value == "radio"

    def test_stress_level_enum_values(self):
        """Test StressLevel enum values."""
        assert StressLevel.LOW.value == "low"
        assert StressLevel.MODERATE.value == "moderate"
        assert StressLevel.HIGH.value == "high"

    def test_pattern_stress_mapping(self):
        """Test pattern type to stress level mapping."""
        assert PATTERN_STRESS_MAP["gank_rotation"] == StressLevel.HIGH
        assert PATTERN_STRESS_MAP["war_target_activity"] == StressLevel.HIGH
        assert PATTERN_STRESS_MAP["npc_faction_activity"] == StressLevel.LOW
        assert PATTERN_STRESS_MAP["repeat_attacker"] == StressLevel.MODERATE
        assert PATTERN_STRESS_MAP["unusual_victim"] == StressLevel.MODERATE


class TestStylePromptConstruction:
    """Tests for style-aware prompt building."""

    @pytest.fixture
    def mock_voice_summary(self):
        """Create mock PersonaVoiceSummary."""
        return PersonaVoiceSummary(
            name="TEST",
            tone="Direct and tactical",
            address_form="Captain",
            example_phrases=["Test phrase"],
            avoid=["Avoid this"],
        )

    def test_conversational_style_includes_guidance(self, mock_voice_summary):
        """Test that conversational style includes appropriate guidance."""
        prompt = build_system_prompt(
            mock_voice_summary,
            style=CommentaryStyle.CONVERSATIONAL,
        )
        assert "STYLE: Conversational" in prompt
        assert "Natural prose" in prompt

    def test_radio_style_includes_guidance(self, mock_voice_summary):
        """Test that radio style includes tactical brevity guidance."""
        prompt = build_system_prompt(
            mock_voice_summary,
            style=CommentaryStyle.RADIO,
            stress_level=StressLevel.HIGH,
            max_chars=150,
        )
        assert "STYLE: Radio operator voice" in prompt
        assert "Subject ellipsis" in prompt
        assert "stress level: high" in prompt.lower()
        assert "150 characters" in prompt

    def test_radio_style_low_stress(self, mock_voice_summary):
        """Test radio style with low stress level."""
        prompt = build_system_prompt(
            mock_voice_summary,
            style=CommentaryStyle.RADIO,
            stress_level=StressLevel.LOW,
        )
        assert "stress level: low" in prompt.lower()

    def test_data_preservation_always_included(self, mock_voice_summary):
        """Test that data preservation rules are always included."""
        for style in CommentaryStyle:
            prompt = build_system_prompt(mock_voice_summary, style=style)
            assert "DATA PRESERVATION" in prompt
            assert "System names: verbatim" in prompt
            assert "ISK values: use the abbreviated format" in prompt
            assert "NEVER invent or guess" in prompt

    def test_persona_voice_included(self, mock_voice_summary):
        """Test that persona voice is included in prompt."""
        prompt = build_system_prompt(mock_voice_summary, style=CommentaryStyle.RADIO)
        assert "PERSONA: TEST" in prompt
        assert "Direct and tactical" in prompt


class TestCommentaryGeneratorStyle:
    """Tests for CommentaryGenerator with style support."""

    @pytest.fixture
    def mock_persona_loader(self):
        """Create mock PersonaLoader."""
        loader = MagicMock(spec=PersonaLoader)
        loader.get_voice_summary.return_value = PersonaVoiceSummary(
            name="TEST",
            tone="Direct and tactical",
            address_form="Captain",
            example_phrases=["Test phrase"],
            avoid=["Avoid this"],
        )
        loader.get_persona_name.return_value = "TEST"
        return loader

    def test_generator_with_style(self, mock_persona_loader):
        """Test generator initialization with style."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-key",
            style=CommentaryStyle.RADIO,
            max_chars=150,
        )
        assert generator._style == CommentaryStyle.RADIO
        assert generator._max_chars == 150

    def test_generator_default_style(self, mock_persona_loader):
        """Test generator defaults to conversational style."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-key",
        )
        assert generator._style == CommentaryStyle.CONVERSATIONAL
        assert generator._max_chars == 200

    def test_create_generator_with_style_config(self, mock_persona_loader):
        """Test factory function with style config."""
        config = {
            "style": "radio",
            "max_chars": 120,
            "api_key": "test-key",
        }
        generator = create_commentary_generator(mock_persona_loader, config)
        assert generator._style == CommentaryStyle.RADIO
        assert generator._max_chars == 120

    def test_create_generator_default_style(self, mock_persona_loader):
        """Test factory function defaults to conversational."""
        generator = create_commentary_generator(mock_persona_loader, {"api_key": "test-key"})
        assert generator._style == CommentaryStyle.CONVERSATIONAL


class TestCommentaryConfigStyle:
    """Tests for CommentaryConfig style fields."""

    def test_config_with_style(self):
        """Test config creation with style."""
        from aria_esi.services.redisq.notifications.config import CommentaryConfig

        config = CommentaryConfig.from_dict({
            "enabled": True,
            "style": "radio",
            "max_chars": 150,
        })
        assert config.style == "radio"
        assert config.max_chars == 150

    def test_config_default_style(self):
        """Test config defaults."""
        from aria_esi.services.redisq.notifications.config import CommentaryConfig

        config = CommentaryConfig.from_dict({})
        assert config.style is None
        assert config.max_chars == 200

    def test_config_validate_style_valid(self):
        """Test style validation passes for valid values."""
        from aria_esi.services.redisq.notifications.config import CommentaryConfig

        config = CommentaryConfig(style="radio")
        errors = config.validate()
        assert not any("style" in e.lower() for e in errors)

        config = CommentaryConfig(style="conversational")
        errors = config.validate()
        assert not any("style" in e.lower() for e in errors)

    def test_config_validate_style_invalid(self):
        """Test style validation fails for invalid values."""
        from aria_esi.services.redisq.notifications.config import CommentaryConfig

        config = CommentaryConfig(style="invalid_style")
        errors = config.validate()
        assert any("Unknown style" in e for e in errors)

    def test_config_validate_max_chars_valid(self):
        """Test max_chars validation passes for valid range."""
        from aria_esi.services.redisq.notifications.config import CommentaryConfig

        config = CommentaryConfig(max_chars=100)
        errors = config.validate()
        assert not any("max_chars" in e for e in errors)

    def test_config_validate_max_chars_too_low(self):
        """Test max_chars validation fails when too low."""
        from aria_esi.services.redisq.notifications.config import CommentaryConfig

        config = CommentaryConfig(max_chars=30)
        errors = config.validate()
        assert any("max_chars must be between 50 and 500" in e for e in errors)

    def test_config_validate_max_chars_too_high(self):
        """Test max_chars validation fails when too high."""
        from aria_esi.services.redisq.notifications.config import CommentaryConfig

        config = CommentaryConfig(max_chars=600)
        errors = config.validate()
        assert any("max_chars must be between 50 and 500" in e for e in errors)


class TestStyleOverrideAtRuntime:
    """Tests for per-call style override during generation."""

    @pytest.fixture
    def mock_persona_loader(self):
        """Create mock PersonaLoader."""
        loader = MagicMock(spec=PersonaLoader)
        loader.get_voice_summary.return_value = PersonaVoiceSummary(
            name="TEST",
            tone="Direct and tactical",
            address_form="Captain",
            example_phrases=["Test phrase"],
            avoid=["Avoid this"],
        )
        loader.get_persona_name.return_value = "TEST"
        return loader

    @pytest.fixture
    def pattern_context(self):
        """Create sample PatternContext."""
        from aria_esi.services.redisq.models import ProcessedKill

        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )
        return PatternContext(
            kill=kill,
            patterns=[
                DetectedPattern(
                    pattern_type="repeat_attacker",
                    description="Same attackers with 4 kills",
                    weight=0.4,
                ),
            ],
            same_attacker_kills_1h=3,
            same_system_kills_1h=5,
        )

    @pytest.mark.asyncio
    async def test_per_call_style_override(self, mock_persona_loader, pattern_context):
        """Test that style can be overridden per-call."""
        # Generator defaults to conversational
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
            style=CommentaryStyle.CONVERSATIONAL,
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Camp active. Eyes open.")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=20)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch.object(generator, "_get_client", return_value=mock_client):
            # Override to radio style for this call
            result = await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
                style=CommentaryStyle.RADIO,
            )

        assert result == "Camp active. Eyes open."

        # Verify the system prompt included radio style guidance
        call_args = mock_client.messages.create.call_args
        system_prompt = call_args.kwargs["system"]
        assert "STYLE: Radio operator voice" in system_prompt
        assert "Subject ellipsis" in system_prompt


class TestStressLevelIntegration:
    """Tests for stress level derivation from pattern context."""

    @pytest.fixture
    def mock_persona_loader(self):
        """Create mock PersonaLoader."""
        loader = MagicMock(spec=PersonaLoader)
        loader.get_voice_summary.return_value = PersonaVoiceSummary(
            name="TEST",
            tone="Direct and tactical",
            address_form="Captain",
            example_phrases=["Test phrase"],
            avoid=["Avoid this"],
        )
        loader.get_persona_name.return_value = "TEST"
        return loader

    def _create_pattern_context(self, pattern_type: str) -> PatternContext:
        """Create PatternContext with specified pattern type."""
        from aria_esi.services.redisq.models import ProcessedKill

        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )
        return PatternContext(
            kill=kill,
            patterns=[
                DetectedPattern(
                    pattern_type=pattern_type,
                    description=f"Test {pattern_type}",
                    weight=0.5,
                ),
            ],
            same_attacker_kills_1h=3,
            same_system_kills_1h=5,
        )

    @pytest.mark.asyncio
    async def test_high_stress_pattern_uses_high_stress_in_prompt(self, mock_persona_loader):
        """Test that gank_rotation (HIGH stress) passes high stress to prompt."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
            style=CommentaryStyle.RADIO,
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Gank rotation active.")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=20)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        pattern_context = self._create_pattern_context("gank_rotation")

        with patch.object(generator, "_get_client", return_value=mock_client):
            await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
            )

        # Verify stress level was passed to prompt
        call_args = mock_client.messages.create.call_args
        system_prompt = call_args.kwargs["system"]
        assert "stress level: high" in system_prompt.lower()

    @pytest.mark.asyncio
    async def test_low_stress_pattern_uses_low_stress_in_prompt(self, mock_persona_loader):
        """Test that npc_faction_activity (LOW stress) passes low stress to prompt."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
            style=CommentaryStyle.RADIO,
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Faction activity noted.")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=20)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        pattern_context = self._create_pattern_context("npc_faction_activity")

        with patch.object(generator, "_get_client", return_value=mock_client):
            await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
            )

        # Verify stress level was passed to prompt
        call_args = mock_client.messages.create.call_args
        system_prompt = call_args.kwargs["system"]
        assert "stress level: low" in system_prompt.lower()

    @pytest.mark.asyncio
    async def test_unknown_pattern_defaults_to_moderate_stress(self, mock_persona_loader):
        """Test that unknown pattern types default to MODERATE stress."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
            style=CommentaryStyle.RADIO,
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Activity noted.")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=20)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        # Use an unknown pattern type
        pattern_context = self._create_pattern_context("unknown_new_pattern")

        with patch.object(generator, "_get_client", return_value=mock_client):
            await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
            )

        # Verify default moderate stress level
        call_args = mock_client.messages.create.call_args
        system_prompt = call_args.kwargs["system"]
        assert "stress level: moderate" in system_prompt.lower()


class TestRadioStyleMaxChars:
    """Tests for radio style max_chars propagation to system prompt."""

    @pytest.fixture
    def mock_voice_summary(self):
        """Create mock PersonaVoiceSummary."""
        return PersonaVoiceSummary(
            name="TEST",
            tone="Direct and tactical",
            address_form="Captain",
            example_phrases=["Test phrase"],
            avoid=["Avoid this"],
        )

    def test_radio_style_reflects_custom_max_chars(self, mock_voice_summary):
        """Test that custom max_chars value appears in radio style prompt."""
        prompt = build_system_prompt(
            mock_voice_summary,
            style=CommentaryStyle.RADIO,
            stress_level=StressLevel.MODERATE,
            max_chars=120,
        )
        assert "120 characters" in prompt
        assert "200 characters" not in prompt

    def test_radio_style_reflects_default_max_chars(self, mock_voice_summary):
        """Test that default max_chars (200) appears in radio style prompt."""
        prompt = build_system_prompt(
            mock_voice_summary,
            style=CommentaryStyle.RADIO,
            stress_level=StressLevel.MODERATE,
            max_chars=200,
        )
        assert "200 characters" in prompt

    def test_radio_style_reflects_high_max_chars(self, mock_voice_summary):
        """Test that high max_chars value appears in radio style prompt."""
        prompt = build_system_prompt(
            mock_voice_summary,
            style=CommentaryStyle.RADIO,
            stress_level=StressLevel.LOW,
            max_chars=350,
        )
        assert "350 characters" in prompt

    def test_conversational_style_has_no_char_limit_in_prompt(self, mock_voice_summary):
        """Test that conversational style doesn't mention character limits."""
        prompt = build_system_prompt(
            mock_voice_summary,
            style=CommentaryStyle.CONVERSATIONAL,
        )
        # Should mention no char limit, be concise
        assert "No character limit" in prompt
        # Should NOT have hard-coded limits from old base prompt
        assert "under 200 characters" not in prompt
        assert "200 characters" not in prompt


class TestMultiPatternStressSelection:
    """Tests for selecting highest-severity stress level from multiple patterns."""

    @pytest.fixture
    def mock_persona_loader(self):
        """Create mock PersonaLoader."""
        loader = MagicMock(spec=PersonaLoader)
        loader.get_voice_summary.return_value = PersonaVoiceSummary(
            name="TEST",
            tone="Direct and tactical",
            address_form="Captain",
            example_phrases=["Test phrase"],
            avoid=["Avoid this"],
        )
        loader.get_persona_name.return_value = "TEST"
        return loader

    def _create_multi_pattern_context(self, pattern_types: list[str]) -> PatternContext:
        """Create PatternContext with multiple pattern types."""
        from aria_esi.services.redisq.models import ProcessedKill

        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )
        patterns = [
            DetectedPattern(
                pattern_type=pt,
                description=f"Test {pt}",
                weight=0.3,
            )
            for pt in pattern_types
        ]
        return PatternContext(
            kill=kill,
            patterns=patterns,
            same_attacker_kills_1h=3,
            same_system_kills_1h=5,
        )

    @pytest.mark.asyncio
    async def test_multiple_patterns_uses_highest_stress(self, mock_persona_loader):
        """Test that multiple patterns select the highest-severity stress level."""

        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
            style=CommentaryStyle.RADIO,
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Multiple threats.")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=20)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        # repeat_attacker (MODERATE) + gank_rotation (HIGH) → should use HIGH
        pattern_context = self._create_multi_pattern_context(
            ["repeat_attacker", "gank_rotation"]
        )

        with patch.object(generator, "_get_client", return_value=mock_client):
            await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
            )

        # Verify highest stress level was used
        call_args = mock_client.messages.create.call_args
        system_prompt = call_args.kwargs["system"]
        assert "stress level: high" in system_prompt.lower()

    @pytest.mark.asyncio
    async def test_low_and_moderate_uses_moderate(self, mock_persona_loader):
        """Test that LOW + MODERATE patterns result in MODERATE stress."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
            style=CommentaryStyle.RADIO,
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Activity noted.")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=20)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        # npc_faction_activity (LOW) + repeat_attacker (MODERATE) → MODERATE
        pattern_context = self._create_multi_pattern_context(
            ["npc_faction_activity", "repeat_attacker"]
        )

        with patch.object(generator, "_get_client", return_value=mock_client):
            await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
            )

        call_args = mock_client.messages.create.call_args
        system_prompt = call_args.kwargs["system"]
        assert "stress level: moderate" in system_prompt.lower()

    @pytest.mark.asyncio
    async def test_order_independence_high_first(self, mock_persona_loader):
        """Test stress selection is order-independent when HIGH pattern is first."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
            style=CommentaryStyle.RADIO,
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Activity noted.")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=20)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        # HIGH first, then LOW - should still use HIGH
        pattern_context = self._create_multi_pattern_context(
            ["war_target_activity", "npc_faction_activity"]
        )

        with patch.object(generator, "_get_client", return_value=mock_client):
            await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
            )

        call_args = mock_client.messages.create.call_args
        system_prompt = call_args.kwargs["system"]
        assert "stress level: high" in system_prompt.lower()

    @pytest.mark.asyncio
    async def test_order_independence_high_last(self, mock_persona_loader):
        """Test stress selection is order-independent when HIGH pattern is last."""
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-api-key",
            style=CommentaryStyle.RADIO,
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Activity noted.")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=20)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        # LOW first, then HIGH - should still use HIGH
        pattern_context = self._create_multi_pattern_context(
            ["npc_faction_activity", "gank_rotation"]
        )

        with patch.object(generator, "_get_client", return_value=mock_client):
            await generator.generate_commentary(
                pattern_context=pattern_context,
                notification_text="Test notification",
            )

        call_args = mock_client.messages.create.call_args
        system_prompt = call_args.kwargs["system"]
        assert "stress level: high" in system_prompt.lower()


class TestValidatePreservedTokens:
    """Tests for protected token validation."""

    def _create_pattern_context(self, total_value: int = 500_000_000) -> PatternContext:
        """Create a PatternContext for testing."""
        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=total_value,
            is_pod_kill=False,
        )
        return PatternContext(
            kill=kill,
            patterns=[],
            same_attacker_kills_1h=0,
            same_system_kills_1h=0,
        )

    def test_valid_output_passes(self):
        """Output with exact tokens passes validation."""
        context = self._create_pattern_context()
        tokens = {"Jita", "Thorax"}
        output = "Gank in Jita. Thorax down."

        assert validate_preserved_tokens(output, context, tokens) is True

    def test_empty_output_passes(self):
        """Empty output passes validation."""
        context = self._create_pattern_context()
        assert validate_preserved_tokens("", context) is True

    def test_no_commentary_passes(self):
        """NO_COMMENTARY signal passes validation."""
        context = self._create_pattern_context()
        assert validate_preserved_tokens("NO_COMMENTARY", context) is True

    def test_corrupted_name_fails(self):
        """Corrupted name (case changed) fails validation."""
        context = self._create_pattern_context()
        tokens = {"Jita"}
        # "jita" instead of "Jita"
        output = "Activity in jita system."

        assert validate_preserved_tokens(output, context, tokens) is False

    def test_missing_token_not_referenced_passes(self):
        """Missing token that isn't referenced passes."""
        context = self._create_pattern_context()
        tokens = {"Jita", "Thorax"}
        # Only mentions Jita, Thorax not referenced
        output = "Camp detected in Jita."

        assert validate_preserved_tokens(output, context, tokens) is True

    def test_extract_protected_tokens_from_pattern_context(self):
        """Tokens are extracted from pattern context dicts, not ProcessedKill fields."""
        # ISK values are intentionally excluded (abbreviated format is lossy)
        # Only names from pattern.context dicts are protected
        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=1_234_567_890,
            is_pod_kill=False,
        )
        context = PatternContext(
            kill=kill,
            patterns=[
                DetectedPattern(
                    pattern_type="test_pattern",
                    description="Test",
                    weight=0.5,
                    context={
                        "system_name": "Amamake",
                        "ship_name": "Thorax",
                        "faction_display": "Serpentis",
                    },
                ),
            ],
            same_attacker_kills_1h=0,
            same_system_kills_1h=0,
        )
        tokens = extract_protected_tokens(context)

        # Names from pattern context ARE extracted
        assert "Amamake" in tokens
        assert "Thorax" in tokens
        assert "Serpentis" in tokens
        # ISK values are NOT extracted (lossy abbreviation)
        assert "1,234,567,890" not in tokens

    def test_extract_protected_tokens_with_passed_names(self):
        """Resolved names passed explicitly are included in protected tokens."""
        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )
        context = PatternContext(
            kill=kill,
            patterns=[],  # No patterns with context
            same_attacker_kills_1h=0,
            same_system_kills_1h=0,
        )

        # Pass resolved names explicitly
        tokens = extract_protected_tokens(
            context,
            system_display="Tama",
            ship_display="Vexor Navy Issue",
        )

        # Passed names ARE extracted
        assert "Tama" in tokens
        assert "Vexor Navy Issue" in tokens

    def test_validate_with_passed_names(self):
        """Validation uses passed names for token checking."""
        context = self._create_pattern_context()

        # Output corrupts "Tama" to "tama"
        output = "Activity in tama. Vexor down."

        # Validation fails because "Tama" (passed) is corrupted to "tama"
        result = validate_preserved_tokens(
            output, context, system_display="Tama", ship_display="Vexor"
        )
        assert result is False

        # Correct output passes
        correct_output = "Activity in Tama. Vexor down."
        result = validate_preserved_tokens(
            correct_output, context, system_display="Tama", ship_display="Vexor"
        )
        assert result is True

    def test_validate_with_fallback_strings(self):
        """Validation works with fallback strings like 'System 30002813'.

        Note: The validator catches case corruption (same letters, different case)
        not value corruption (completely different strings). This is by design -
        the LLM might legitimately choose not to reference a value.
        """
        context = self._create_pattern_context()

        # When names aren't resolved, fallback strings should be protected
        # This simulates what manager.py passes: "System {id}" / "Ship {type_id}"
        system_display = "System 30002813"
        ship_display = "Ship 17740"

        # Output that corrupts the case of the fallback string
        corrupted_output = "Activity in system 30002813. ship 17740 destroyed."
        result = validate_preserved_tokens(
            corrupted_output, context, system_display=system_display, ship_display=ship_display
        )
        assert result is False

        # Correct output passes (exact case match)
        correct_output = "Activity in System 30002813. Ship 17740 destroyed."
        result = validate_preserved_tokens(
            correct_output, context, system_display=system_display, ship_display=ship_display
        )
        assert result is True

        # Output that doesn't reference the value at all passes
        # (LLM might simply not mention it)
        unreferenced_output = "Hostile activity detected."
        result = validate_preserved_tokens(
            unreferenced_output, context, system_display=system_display, ship_display=ship_display
        )
        assert result is True

    def test_validate_with_capsule_fallback(self):
        """Validation works with 'Capsule' fallback for pod kills."""
        context = self._create_pattern_context()

        # For pod kills, ship_display is "Capsule"
        system_display = "Tama"
        ship_display = "Capsule"

        # Output that changes "Capsule" case
        corrupted_output = "capsule destroyed in Tama."
        result = validate_preserved_tokens(
            corrupted_output, context, system_display=system_display, ship_display=ship_display
        )
        assert result is False

        # Correct output passes
        correct_output = "Capsule destroyed in Tama."
        result = validate_preserved_tokens(
            correct_output, context, system_display=system_display, ship_display=ship_display
        )
        assert result is True


class TestPerCallMaxCharsOverride:
    """Tests for per-call max_chars override in generate_commentary."""

    @pytest.fixture
    def mock_persona_loader(self):
        """Create mock PersonaLoader."""
        loader = MagicMock(spec=PersonaLoader)
        loader.get_voice_summary.return_value = PersonaVoiceSummary(
            name="TEST",
            tone="Direct",
            address_form="Captain",
            example_phrases=["Test"],
            avoid=["Avoid"],
        )
        return loader

    def test_per_call_max_chars_in_prompt_builder(self, mock_persona_loader):
        """Per-call max_chars reflects in built prompt."""
        from aria_esi.services.redisq.notifications.prompts import build_system_prompt

        # When building prompt with different max_chars, it should reflect in prompt
        voice_summary = mock_persona_loader.get_voice_summary()
        prompt_default = build_system_prompt(
            voice_summary,
            style=CommentaryStyle.RADIO,
            max_chars=200,
        )
        prompt_override = build_system_prompt(
            voice_summary,
            style=CommentaryStyle.RADIO,
            max_chars=150,
        )

        assert "under 200 characters" in prompt_default
        assert "under 150 characters" in prompt_override

    @pytest.mark.asyncio
    async def test_per_call_max_chars_threaded_to_llm(self, mock_persona_loader):
        """Per-call max_chars is threaded through generate_commentary to LLM call."""
        # Create generator with default max_chars=200
        generator = CommentaryGenerator(
            persona_loader=mock_persona_loader,
            api_key="test-key",
            style=CommentaryStyle.RADIO,
            max_chars=200,
        )

        # Create pattern context
        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )
        pattern_context = PatternContext(
            kill=kill,
            patterns=[],
            same_attacker_kills_1h=0,
            same_system_kills_1h=0,
        )

        # Mock the Anthropic client to capture the system prompt
        captured_system_prompt = None

        async def mock_create(**kwargs):
            nonlocal captured_system_prompt
            captured_system_prompt = kwargs.get("system")
            # Return a mock response
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Test commentary.")]
            mock_response.usage = MagicMock(input_tokens=100, output_tokens=20)
            return mock_response

        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        generator._client = mock_client

        # Call with per-call override of max_chars=150
        await generator.generate_commentary(
            pattern_context=pattern_context,
            notification_text="Test notification",
            max_chars=150,  # Override from 200 to 150
        )

        # Verify the override was used in the prompt
        assert captured_system_prompt is not None
        assert "under 150 characters" in captured_system_prompt
        assert "under 200 characters" not in captured_system_prompt


class TestSeverityBasedStressDerivation:
    """Tests for severity-based stress level derivation."""

    def _create_pattern_context_with_severity(
        self, severity: PatternSeverity
    ) -> PatternContext:
        """Create PatternContext with a pattern that has severity metadata."""
        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )
        return PatternContext(
            kill=kill,
            patterns=[
                DetectedPattern(
                    pattern_type="new_future_pattern",
                    description="A new pattern type",
                    weight=0.3,
                    severity=severity,
                ),
            ],
            same_attacker_kills_1h=0,
            same_system_kills_1h=0,
        )

    def test_critical_severity_returns_high_stress(self):
        """CRITICAL severity returns HIGH stress level."""
        context = self._create_pattern_context_with_severity(PatternSeverity.CRITICAL)
        assert get_stress_level(context) == StressLevel.HIGH

    def test_warning_severity_returns_moderate_stress(self):
        """WARNING severity returns MODERATE stress level."""
        context = self._create_pattern_context_with_severity(PatternSeverity.WARNING)
        assert get_stress_level(context) == StressLevel.MODERATE

    def test_info_severity_returns_low_stress(self):
        """INFO severity returns LOW stress level."""
        context = self._create_pattern_context_with_severity(PatternSeverity.INFO)
        assert get_stress_level(context) == StressLevel.LOW

    def test_no_severity_falls_back_to_pattern_map(self):
        """Patterns without severity fall back to PATTERN_STRESS_MAP."""
        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )
        context = PatternContext(
            kill=kill,
            patterns=[
                DetectedPattern(
                    pattern_type="gank_rotation",
                    description="Gank rotation",
                    weight=0.5,
                    severity=None,  # No severity metadata
                ),
            ],
            same_attacker_kills_1h=0,
            same_system_kills_1h=0,
        )
        # Should fall back to PATTERN_STRESS_MAP["gank_rotation"] = HIGH
        assert get_stress_level(context) == StressLevel.HIGH

    def test_mixed_severity_and_no_severity_uses_highest(self):
        """Mixed patterns use highest stress level."""
        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )
        context = PatternContext(
            kill=kill,
            patterns=[
                # INFO severity → LOW stress
                DetectedPattern(
                    pattern_type="npc_faction_activity",
                    description="NPC activity",
                    weight=0.3,
                    severity=PatternSeverity.INFO,
                ),
                # No severity, uses map → HIGH stress
                DetectedPattern(
                    pattern_type="gank_rotation",
                    description="Gank rotation",
                    weight=0.5,
                    severity=None,
                ),
            ],
            same_attacker_kills_1h=0,
            same_system_kills_1h=0,
        )
        # Should use highest: HIGH
        assert get_stress_level(context) == StressLevel.HIGH

    def test_empty_patterns_returns_moderate(self):
        """Empty patterns list returns MODERATE stress."""
        kill = ProcessedKill(
            kill_id=12345678,
            kill_time=datetime.now(),
            solar_system_id=30002813,
            victim_ship_type_id=17740,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
            attacker_count=5,
            attacker_corps=[98000002],
            attacker_alliances=[],
            attacker_ship_types=[11993],
            final_blow_ship_type_id=11993,
            total_value=500_000_000,
            is_pod_kill=False,
        )
        context = PatternContext(
            kill=kill,
            patterns=[],
            same_attacker_kills_1h=0,
            same_system_kills_1h=0,
        )
        assert get_stress_level(context) == StressLevel.MODERATE
