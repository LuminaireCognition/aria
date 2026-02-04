"""
Tests for notification configuration classes.

Tests CommentaryConfig, QuietHoursConfig, NPCFactionKillConfig,
PoliticalEntityKillConfig, TopologyConfig, and TriggerConfig.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from aria_esi.services.redisq.notifications.config import (
    CommentaryConfig,
    NPCFactionKillConfig,
    PoliticalEntityKillConfig,
    QuietHoursConfig,
    TopologyConfig,
    TriggerConfig,
)


class TestCommentaryConfig:
    """Tests for CommentaryConfig dataclass."""

    def test_default_values(self):
        """Default values are sensible."""
        config = CommentaryConfig()
        assert config.enabled is False
        assert config.model == "claude-sonnet-4-5-20241022"
        assert config.timeout_ms == 3000
        assert config.max_tokens == 100
        assert config.warrant_threshold == 0.3
        assert config.cost_limit_daily_usd == 1.0
        assert config.persona is None
        assert config.style is None
        assert config.max_chars == 200  # DEFAULT_MAX_CHARS

    def test_from_dict_empty(self):
        """from_dict with None returns defaults."""
        config = CommentaryConfig.from_dict(None)
        assert config.enabled is False

    def test_from_dict_full(self):
        """from_dict parses all fields."""
        data = {
            "enabled": True,
            "model": "custom-model",
            "timeout_ms": 5000,
            "max_tokens": 150,
            "warrant_threshold": 0.5,
            "cost_limit_daily_usd": 2.0,
            "persona": "paria",
            "style": "radio",
            "max_chars": 180,
        }
        config = CommentaryConfig.from_dict(data)

        assert config.enabled is True
        assert config.model == "custom-model"
        assert config.timeout_ms == 5000
        assert config.max_tokens == 150
        assert config.warrant_threshold == 0.5
        assert config.cost_limit_daily_usd == 2.0
        assert config.persona == "paria"
        assert config.style == "radio"
        assert config.max_chars == 180


class TestCommentaryConfigValidation:
    """Tests for CommentaryConfig validation."""

    def test_validate_valid_config(self):
        """Valid config has no errors."""
        config = CommentaryConfig(enabled=True)
        errors = config.validate()
        assert errors == []

    def test_validate_timeout_too_low(self):
        """Timeout below 500ms is invalid."""
        config = CommentaryConfig(timeout_ms=200)
        errors = config.validate()
        assert any("timeout_ms must be >= 500" in e for e in errors)

    def test_validate_timeout_too_high(self):
        """Timeout above 10000ms is invalid."""
        config = CommentaryConfig(timeout_ms=15000)
        errors = config.validate()
        assert any("timeout_ms must be <= 10000" in e for e in errors)

    def test_validate_warrant_threshold_too_low(self):
        """Warrant threshold below 0 is invalid."""
        config = CommentaryConfig(warrant_threshold=-0.5)
        errors = config.validate()
        assert any("warrant_threshold must be between 0 and 1" in e for e in errors)

    def test_validate_warrant_threshold_too_high(self):
        """Warrant threshold above 1 is invalid."""
        config = CommentaryConfig(warrant_threshold=1.5)
        errors = config.validate()
        assert any("warrant_threshold must be between 0 and 1" in e for e in errors)

    def test_validate_negative_cost_limit(self):
        """Negative cost limit is invalid."""
        config = CommentaryConfig(cost_limit_daily_usd=-1.0)
        errors = config.validate()
        assert any("cost_limit_daily_usd must be non-negative" in e for e in errors)

    def test_validate_invalid_persona(self):
        """Invalid persona is rejected."""
        with patch(
            "aria_esi.services.redisq.notifications.persona.VOICE_SUMMARIES",
            {"aria": {}, "paria": {}},
        ):
            config = CommentaryConfig(persona="invalid-persona")
            errors = config.validate()
            assert any("Unknown persona" in e for e in errors)

    def test_validate_valid_persona(self):
        """Valid persona is accepted."""
        with patch(
            "aria_esi.services.redisq.notifications.persona.VOICE_SUMMARIES",
            {"aria": {}, "paria": {}},
        ):
            config = CommentaryConfig(persona="paria")
            errors = config.validate()
            assert not any("persona" in e.lower() for e in errors)

    def test_validate_invalid_style(self):
        """Invalid style is rejected."""
        config = CommentaryConfig(style="invalid")
        errors = config.validate()
        assert any("Unknown style" in e for e in errors)

    def test_validate_valid_styles(self):
        """Valid styles are accepted."""
        for style in ["conversational", "radio"]:
            config = CommentaryConfig(style=style)
            errors = config.validate()
            assert not any("style" in e.lower() for e in errors)

    def test_validate_max_chars_too_low(self):
        """max_chars below 50 is invalid."""
        config = CommentaryConfig(max_chars=30)
        errors = config.validate()
        assert any("max_chars must be between 50 and 500" in e for e in errors)

    def test_validate_max_chars_too_high(self):
        """max_chars above 500 is invalid."""
        config = CommentaryConfig(max_chars=600)
        errors = config.validate()
        assert any("max_chars must be between 50 and 500" in e for e in errors)


class TestQuietHoursConfig:
    """Tests for QuietHoursConfig dataclass."""

    def test_default_values(self):
        """Default values are sensible."""
        config = QuietHoursConfig()
        assert config.enabled is False
        assert config.start == "02:00"
        assert config.end == "08:00"
        assert config.timezone == "America/New_York"

    def test_from_dict_empty(self):
        """from_dict with None returns defaults."""
        config = QuietHoursConfig.from_dict(None)
        assert config.enabled is False
        assert config.start == "02:00"

    def test_from_dict_full(self):
        """from_dict parses all fields."""
        data = {
            "enabled": True,
            "start": "03:00",
            "end": "09:00",
            "timezone": "UTC",
        }
        config = QuietHoursConfig.from_dict(data)

        assert config.enabled is True
        assert config.start == "03:00"
        assert config.end == "09:00"
        assert config.timezone == "UTC"

    def test_from_dict_partial(self):
        """from_dict handles partial data."""
        data = {"enabled": True}
        config = QuietHoursConfig.from_dict(data)

        assert config.enabled is True
        assert config.start == "02:00"  # Default
        assert config.end == "08:00"  # Default


class TestNPCFactionKillConfig:
    """Tests for NPCFactionKillConfig dataclass."""

    def test_default_values(self):
        """Default values are sensible."""
        config = NPCFactionKillConfig()
        assert config.enabled is False
        assert config.factions == []
        assert config.as_attacker is True
        assert config.as_victim is False
        assert config.ignore_topology is True

    def test_from_dict_empty(self):
        """from_dict with None returns defaults."""
        config = NPCFactionKillConfig.from_dict(None)
        assert config.enabled is False

    def test_from_dict_full(self):
        """from_dict parses all fields."""
        data = {
            "enabled": True,
            "factions": ["serpentis", "angel_cartel"],
            "as_attacker": True,
            "as_victim": True,
            "ignore_topology": False,
        }
        config = NPCFactionKillConfig.from_dict(data)

        assert config.enabled is True
        assert config.factions == ["serpentis", "angel_cartel"]
        assert config.as_attacker is True
        assert config.as_victim is True
        assert config.ignore_topology is False

    def test_to_dict(self):
        """to_dict serializes correctly."""
        config = NPCFactionKillConfig(
            enabled=True,
            factions=["serpentis"],
            as_attacker=True,
            as_victim=False,
            ignore_topology=True,
        )
        data = config.to_dict()

        assert data["enabled"] is True
        assert data["factions"] == ["serpentis"]
        assert data["as_attacker"] is True
        assert data["as_victim"] is False
        assert data["ignore_topology"] is True


class TestNPCFactionKillConfigValidation:
    """Tests for NPCFactionKillConfig validation."""

    def test_validate_valid_config(self):
        """Valid config has no errors."""
        config = NPCFactionKillConfig(
            enabled=True,
            factions=["serpentis"],
            as_attacker=True,
        )
        errors = config.validate()
        assert errors == []

    def test_validate_enabled_no_factions(self):
        """Enabled with no factions is invalid."""
        config = NPCFactionKillConfig(
            enabled=True,
            factions=[],
        )
        errors = config.validate()
        assert any("factions must not be empty" in e for e in errors)

    def test_validate_enabled_no_role(self):
        """Enabled with neither attacker nor victim is invalid."""
        config = NPCFactionKillConfig(
            enabled=True,
            factions=["serpentis"],
            as_attacker=False,
            as_victim=False,
        )
        errors = config.validate()
        assert any("as_attacker or as_victim" in e for e in errors)

    def test_validate_unknown_faction(self):
        """Unknown faction is rejected when reference provided."""
        config = NPCFactionKillConfig(
            enabled=True,
            factions=["unknown_faction"],
        )
        errors = config.validate(valid_factions=["serpentis", "angel_cartel"])
        assert any("Unknown faction" in e for e in errors)

    def test_validate_faction_case_insensitive(self):
        """Faction validation is case-insensitive."""
        config = NPCFactionKillConfig(
            enabled=True,
            factions=["SERPENTIS"],
        )
        errors = config.validate(valid_factions=["serpentis", "angel_cartel"])
        # Should not have unknown faction error
        assert not any("Unknown faction" in e for e in errors)


class TestPoliticalEntityKillConfig:
    """Tests for PoliticalEntityKillConfig dataclass."""

    def test_default_values(self):
        """Default values are sensible."""
        config = PoliticalEntityKillConfig()
        assert config.enabled is False
        assert config.corporations == []
        assert config.alliances == []
        assert config.as_attacker is True
        assert config.as_victim is True
        assert config.min_value == 0

    def test_from_dict_full(self):
        """from_dict parses all fields."""
        data = {
            "enabled": True,
            "corporations": [98000001, "Test Corp"],
            "alliances": [99000001],
            "as_attacker": True,
            "as_victim": False,
            "min_value": 100_000_000,
        }
        config = PoliticalEntityKillConfig.from_dict(data)

        assert config.enabled is True
        assert config.corporations == [98000001, "Test Corp"]
        assert config.alliances == [99000001]
        assert config.as_attacker is True
        assert config.as_victim is False
        assert config.min_value == 100_000_000

    def test_to_dict(self):
        """to_dict serializes correctly."""
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[98000001],
            alliances=[99000001],
            min_value=50_000_000,
        )
        data = config.to_dict()

        assert data["enabled"] is True
        assert data["corporations"] == [98000001]
        assert data["alliances"] == [99000001]
        assert data["min_value"] == 50_000_000

    def test_has_entities_empty(self):
        """has_entities is False when no entities configured."""
        config = PoliticalEntityKillConfig(enabled=True)
        assert config.has_entities is False

    def test_has_entities_with_corps(self):
        """has_entities is True when corporations configured."""
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[98000001],
        )
        assert config.has_entities is True

    def test_has_entities_with_alliances(self):
        """has_entities is True when alliances configured."""
        config = PoliticalEntityKillConfig(
            enabled=True,
            alliances=[99000001],
        )
        assert config.has_entities is True


class TestPoliticalEntityKillConfigValidation:
    """Tests for PoliticalEntityKillConfig validation."""

    def test_validate_valid_config(self):
        """Valid config has no errors."""
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[98000001],
        )
        errors = config.validate()
        assert errors == []

    def test_validate_enabled_no_entities(self):
        """Enabled with no entities is invalid."""
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[],
            alliances=[],
        )
        errors = config.validate()
        assert any("at least one corporation or alliance" in e for e in errors)

    def test_validate_enabled_no_role(self):
        """Enabled with neither attacker nor victim is invalid."""
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[98000001],
            as_attacker=False,
            as_victim=False,
        )
        errors = config.validate()
        assert any("as_attacker or as_victim" in e for e in errors)

    def test_validate_negative_min_value(self):
        """Negative min_value is invalid."""
        config = PoliticalEntityKillConfig(
            enabled=True,
            corporations=[98000001],
            min_value=-100,
        )
        errors = config.validate()
        assert any("min_value must be non-negative" in e for e in errors)


class TestTriggerConfig:
    """Tests for TriggerConfig dataclass."""

    def test_default_values(self):
        """Default values are sensible."""
        config = TriggerConfig()
        assert config.watchlist_activity is True
        assert config.gatecamp_detected is True
        assert config.high_value_threshold == 1_000_000_000
        assert config.war_activity is False
        assert config.war_suppress_gatecamp is True
        assert config.npc_faction_kill.enabled is False
        assert config.political_entity.enabled is False

    def test_from_dict_empty(self):
        """from_dict with None returns defaults."""
        config = TriggerConfig.from_dict(None)
        assert config.watchlist_activity is True

    def test_from_dict_full(self):
        """from_dict parses all fields including nested configs."""
        data = {
            "watchlist_activity": False,
            "gatecamp_detected": False,
            "high_value_threshold": 500_000_000,
            "war_activity": True,
            "war_suppress_gatecamp": False,
            "npc_faction_kill": {
                "enabled": True,
                "factions": ["serpentis"],
            },
            "political_entity": {
                "enabled": True,
                "corporations": [98000001],
            },
        }
        config = TriggerConfig.from_dict(data)

        assert config.watchlist_activity is False
        assert config.gatecamp_detected is False
        assert config.high_value_threshold == 500_000_000
        assert config.war_activity is True
        assert config.war_suppress_gatecamp is False
        assert config.npc_faction_kill.enabled is True
        assert config.npc_faction_kill.factions == ["serpentis"]
        assert config.political_entity.enabled is True
        assert config.political_entity.corporations == [98000001]


class TestTopologyConfig:
    """Tests for TopologyConfig dataclass."""

    def test_default_values(self):
        """Default values are sensible."""
        config = TopologyConfig()
        assert config.enabled is False
        assert config.operational_systems == []
        assert "operational" in config.interest_weights
        assert config.interest_weights["operational"] == 1.0

    def test_from_dict_empty(self):
        """from_dict with None returns defaults."""
        config = TopologyConfig.from_dict(None)
        assert config.enabled is False

    def test_from_dict_full(self):
        """from_dict parses all fields."""
        data = {
            "enabled": True,
            "operational_systems": ["Jita", "Perimeter"],
            "interest_weights": {
                "operational": 0.8,
                "hop_1": 0.6,
                "hop_2": 0.4,
            },
        }
        config = TopologyConfig.from_dict(data)

        assert config.enabled is True
        assert config.operational_systems == ["Jita", "Perimeter"]
        assert config.interest_weights["operational"] == 0.8


class TestTopologyConfigValidation:
    """Tests for TopologyConfig validation."""

    def test_validate_valid_config(self):
        """Valid config has no errors."""
        config = TopologyConfig(
            enabled=True,
            operational_systems=["Jita"],
        )
        errors = config.validate()
        assert errors == []

    def test_validate_enabled_no_systems(self):
        """Enabled with no systems is invalid."""
        config = TopologyConfig(
            enabled=True,
            operational_systems=[],
        )
        errors = config.validate()
        assert any("must be non-empty" in e for e in errors)

    def test_validate_unknown_weight_key(self):
        """Unknown weight key is invalid."""
        config = TopologyConfig(
            enabled=True,
            operational_systems=["Jita"],
            interest_weights={
                "operational": 1.0,
                "invalid_key": 0.5,
            },
        )
        errors = config.validate()
        assert any("Unknown interest weight key" in e for e in errors)

    def test_validate_weight_out_of_range(self):
        """Weight outside 0-1 range is invalid."""
        config = TopologyConfig(
            enabled=True,
            operational_systems=["Jita"],
            interest_weights={
                "operational": 1.5,  # Too high
            },
        )
        errors = config.validate()
        assert any("must be between 0 and 1" in e for e in errors)

    def test_validate_negative_weight(self):
        """Negative weight is invalid."""
        config = TopologyConfig(
            enabled=True,
            operational_systems=["Jita"],
            interest_weights={
                "operational": -0.5,
            },
        )
        errors = config.validate()
        assert any("must be between 0 and 1" in e for e in errors)


class TestTopologyConfigLoad:
    """Tests for TopologyConfig.load() method."""

    def test_load_missing_file(self):
        """Load with missing file returns empty config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp dir where config.json doesn't exist
            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                config = TopologyConfig.load()
            finally:
                os.chdir(old_cwd)

        assert config.enabled is False

    def test_load_invalid_json(self):
        """Load with invalid JSON returns empty config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "userdata" / "config.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("{{invalid json")

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                config = TopologyConfig.load()
            finally:
                os.chdir(old_cwd)

        assert config.enabled is False

    def test_load_valid_config(self):
        """Load with valid config file works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "userdata" / "config.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "redisq": {
                            "topology": {
                                "enabled": True,
                                "operational_systems": ["Jita"],
                            }
                        }
                    }
                )
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                config = TopologyConfig.load()
            finally:
                os.chdir(old_cwd)

        assert config.enabled is True
        assert config.operational_systems == ["Jita"]
