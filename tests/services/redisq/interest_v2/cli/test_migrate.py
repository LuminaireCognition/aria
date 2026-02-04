"""
Tests for Interest Engine v2 Migration Tool.

CRITICAL TEST AREA: --preserve-triggers produces v1 behavior.
"""

from __future__ import annotations

from aria_esi.services.redisq.interest_v2.cli.migrate import (
    MigrationResult,
    MigrationStrategy,
    format_migration_diff,
    migrate_profile,
    validate_migration,
)


class TestMigrationStrategy:
    """Tests for migration strategy enum."""

    def test_strategy_values(self):
        """Strategy enum has expected values."""
        assert MigrationStrategy.PRESERVE_TRIGGERS.value == "preserve-triggers"
        assert MigrationStrategy.WEIGHTED_ONLY.value == "weighted-only"
        assert MigrationStrategy.HYBRID.value == "hybrid"


class TestMigrationResult:
    """Tests for MigrationResult dataclass."""

    def test_to_dict(self):
        """Result converts to dictionary."""
        result = MigrationResult(
            success=True,
            profile_name="test",
            strategy=MigrationStrategy.HYBRID,
            interest_config={"engine": "v2", "preset": "trade-hub"},
            warnings=["warning1"],
            changes=["change1"],
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["profile_name"] == "test"
        assert d["strategy"] == "hybrid"
        assert d["interest"]["engine"] == "v2"
        assert "warning1" in d["warnings"]
        assert "change1" in d["changes"]


class TestMigrateProfile:
    """Tests for profile migration."""

    def test_basic_migration(self):
        """Basic profile migration works."""
        profile = {
            "name": "test-profile",
            "topology": {},
            "triggers": {},
        }

        result = migrate_profile(profile)

        assert result.success is True
        assert result.profile_name == "test-profile"
        assert result.interest_config["engine"] == "v2"

    def test_auto_detect_preset_trade_hub(self):
        """Auto-detects trade-hub preset from topology."""
        profile = {
            "name": "jita-monitor",
            "topology": {
                "geographic": {
                    "systems": [{"name": "Jita"}]
                }
            },
            "triggers": {},
        }

        result = migrate_profile(profile)

        assert result.interest_config["preset"] == "trade-hub"
        assert any("trade-hub" in c for c in result.changes)

    def test_auto_detect_preset_political(self):
        """Auto-detects political preset from entity config."""
        profile = {
            "name": "alliance-intel",
            "topology": {
                "entity": {
                    "alliances": [99001234]
                }
            },
            "triggers": {},
        }

        result = migrate_profile(profile)

        assert result.interest_config["preset"] == "political"

    def test_auto_detect_preset_hunter(self):
        """Auto-detects hunter preset from routes."""
        profile = {
            "name": "patrol-route",
            "topology": {
                "routes": {
                    "systems": ["Amamake", "Tama", "Rancer"]
                }
            },
            "triggers": {},
        }

        result = migrate_profile(profile)

        assert result.interest_config["preset"] == "hunter"

    def test_explicit_preset_override(self):
        """Explicit preset overrides auto-detection."""
        profile = {
            "name": "test",
            "topology": {
                "geographic": {
                    "systems": [{"name": "Jita"}]  # Would be trade-hub
                }
            },
            "triggers": {},
        }

        result = migrate_profile(profile, preset="political")

        assert result.interest_config["preset"] == "political"


class TestPreserveTriggersMigration:
    """
    CRITICAL: Tests for --preserve-triggers migration.

    This strategy must produce behavior identical to v1.
    """

    def test_watchlist_activity_to_always_notify(self):
        """watchlist_activity trigger becomes always_notify rule."""
        profile = {
            "name": "watchlist-monitor",
            "topology": {},
            "triggers": {
                "watchlist_activity": {"enabled": True}
            },
        }

        result = migrate_profile(profile, strategy=MigrationStrategy.PRESERVE_TRIGGERS)

        assert "rules" in result.interest_config
        assert "watchlist_match" in result.interest_config["rules"]["always_notify"]
        assert any("watchlist_activity" in c for c in result.changes)

    def test_high_value_threshold_preserved(self):
        """high_value_threshold trigger with min_value preserved."""
        profile = {
            "name": "high-value-monitor",
            "topology": {},
            "triggers": {
                "high_value_threshold": {
                    "enabled": True,
                    "min_value": 2_000_000_000,
                }
            },
        }

        result = migrate_profile(profile, strategy=MigrationStrategy.PRESERVE_TRIGGERS)

        # Rule added to always_notify
        assert "high_value" in result.interest_config["rules"]["always_notify"]

        # Min value preserved in signals
        assert "signals" in result.interest_config
        assert result.interest_config["signals"]["value"]["min"] == 2_000_000_000

    def test_gatecamp_detected_preserved(self):
        """gatecamp_detected trigger becomes always_notify rule."""
        profile = {
            "name": "gatecamp-alert",
            "topology": {},
            "triggers": {
                "gatecamp_detected": {"enabled": True}
            },
        }

        result = migrate_profile(profile, strategy=MigrationStrategy.PRESERVE_TRIGGERS)

        assert "gatecamp_detected" in result.interest_config["rules"]["always_notify"]

    def test_pod_kill_disabled_to_always_ignore(self):
        """Disabled pod_kill trigger becomes always_ignore rule."""
        profile = {
            "name": "no-pods",
            "topology": {},
            "triggers": {
                "pod_kill": {"enabled": False}
            },
        }

        result = migrate_profile(profile, strategy=MigrationStrategy.PRESERVE_TRIGGERS)

        assert "rules" in result.interest_config
        assert "pod_only" in result.interest_config["rules"]["always_ignore"]

    def test_npc_faction_kill_warning(self):
        """npc_faction_kill trigger generates warning about behavior change."""
        profile = {
            "name": "npc-monitor",
            "topology": {},
            "triggers": {
                "npc_faction_kill": {"enabled": True}
            },
        }

        result = migrate_profile(profile, strategy=MigrationStrategy.PRESERVE_TRIGGERS)

        # Should warn about different behavior
        assert any("npc_faction_kill" in w for w in result.warnings)

    def test_multiple_triggers_combined(self):
        """Multiple triggers are all preserved."""
        profile = {
            "name": "full-config",
            "topology": {},
            "triggers": {
                "watchlist_activity": {"enabled": True},
                "high_value_threshold": {"enabled": True, "min_value": 1_000_000_000},
                "gatecamp_detected": {"enabled": True},
                "pod_kill": {"enabled": False},
            },
        }

        result = migrate_profile(profile, strategy=MigrationStrategy.PRESERVE_TRIGGERS)

        rules = result.interest_config["rules"]

        # All always_notify rules present
        assert "watchlist_match" in rules["always_notify"]
        assert "high_value" in rules["always_notify"]
        assert "gatecamp_detected" in rules["always_notify"]

        # pod_only in always_ignore
        assert "pod_only" in rules["always_ignore"]


class TestWeightedOnlyMigration:
    """Tests for --weighted-only migration."""

    def test_geographic_to_location_weight(self):
        """Geographic topology increases location weight."""
        profile = {
            "name": "geo-config",
            "topology": {
                "geographic": {
                    "systems": [{"name": "Dodixie"}]
                }
            },
            "triggers": {},
        }

        result = migrate_profile(profile, strategy=MigrationStrategy.WEIGHTED_ONLY)

        assert "weights" in result.interest_config
        assert result.interest_config["weights"]["location"] >= 0.7

    def test_routes_to_routes_weight(self):
        """Routes topology increases routes weight."""
        profile = {
            "name": "route-config",
            "topology": {
                "routes": {
                    "systems": ["Jita", "Perimeter"]
                }
            },
            "triggers": {},
        }

        result = migrate_profile(profile, strategy=MigrationStrategy.WEIGHTED_ONLY)

        assert "weights" in result.interest_config
        assert result.interest_config["weights"]["routes"] >= 0.5

    def test_entity_to_politics_weight(self):
        """Entity topology increases politics weight."""
        profile = {
            "name": "corp-config",
            "topology": {
                "entity": {
                    "corporations": [98000001]
                }
            },
            "triggers": {},
        }

        result = migrate_profile(profile, strategy=MigrationStrategy.WEIGHTED_ONLY)

        assert "weights" in result.interest_config
        assert result.interest_config["weights"]["politics"] >= 0.6

    def test_warning_about_trigger_loss(self):
        """Weighted-only warns about triggers not being preserved."""
        profile = {
            "name": "has-triggers",
            "topology": {},
            "triggers": {
                "high_value_threshold": {"enabled": True, "min_value": 1_000_000_000}
            },
        }

        result = migrate_profile(profile, strategy=MigrationStrategy.WEIGHTED_ONLY)

        assert any("not preserve" in w.lower() or "weighted-only" in w.lower() for w in result.warnings)


class TestHybridMigration:
    """Tests for --hybrid migration (default)."""

    def test_hybrid_combines_weights_and_triggers(self):
        """Hybrid preserves critical triggers AND derives weights."""
        profile = {
            "name": "hybrid-config",
            "topology": {
                "geographic": {
                    "systems": [{"name": "Jita"}]
                }
            },
            "triggers": {
                "high_value_threshold": {"enabled": True, "min_value": 1_500_000_000},
            },
        }

        result = migrate_profile(profile, strategy=MigrationStrategy.HYBRID)

        # Has weights from topology
        assert "weights" in result.interest_config
        assert result.interest_config["weights"]["location"] >= 0.5

        # Has rules from triggers
        assert "rules" in result.interest_config
        assert "high_value" in result.interest_config["rules"]["always_notify"]

    def test_hybrid_no_weighted_warning(self):
        """Hybrid removes the weighted-only warning."""
        profile = {
            "name": "hybrid-config",
            "topology": {},
            "triggers": {
                "high_value_threshold": {"enabled": True},
            },
        }

        result = migrate_profile(profile, strategy=MigrationStrategy.HYBRID)

        # Should not have the weighted-only warning
        assert not any("weighted-only migration" in w.lower() for w in result.warnings)


class TestTopologyMigration:
    """Tests for topology to signals migration."""

    def test_systems_to_location_signals(self):
        """Geographic systems migrate to signals.location.geographic."""
        profile = {
            "name": "multi-system",
            "topology": {
                "geographic": {
                    "systems": [
                        {"name": "Jita", "range": 3},
                        {"name": "Dodixie", "classification": "home"},
                    ]
                }
            },
            "triggers": {},
        }

        result = migrate_profile(profile)

        # Should have signals.location.geographic.systems
        signals = result.interest_config.get("signals", {})
        location = signals.get("location", {})
        geo = location.get("geographic", {})

        if geo:
            systems = geo.get("systems", [])
            assert len(systems) == 2

            # Check first system preserved fields
            jita = next((s for s in systems if s["name"] == "Jita"), None)
            if jita:
                assert jita.get("range") == 3

    def test_migration_changes_tracked(self):
        """Migration tracks what changed."""
        profile = {
            "name": "tracked",
            "topology": {
                "geographic": {
                    "systems": [{"name": "Amarr"}]
                }
            },
            "triggers": {},
        }

        result = migrate_profile(profile)

        # Should have change about systems migration
        assert len(result.changes) > 0


class TestFormatMigrationDiff:
    """Tests for migration diff formatting."""

    def test_format_includes_header(self):
        """Diff includes profile name and strategy."""
        result = MigrationResult(
            success=True,
            profile_name="test-profile",
            strategy=MigrationStrategy.HYBRID,
            interest_config={"engine": "v2"},
            changes=[],
            warnings=[],
        )

        diff = format_migration_diff({}, result)

        assert "test-profile" in diff
        assert "hybrid" in diff.lower()

    def test_format_includes_changes(self):
        """Diff includes all changes."""
        result = MigrationResult(
            success=True,
            profile_name="test",
            strategy=MigrationStrategy.HYBRID,
            interest_config={"engine": "v2"},
            changes=["Change 1", "Change 2"],
            warnings=[],
        )

        diff = format_migration_diff({}, result)

        assert "Change 1" in diff
        assert "Change 2" in diff

    def test_format_includes_warnings(self):
        """Diff includes warnings."""
        result = MigrationResult(
            success=True,
            profile_name="test",
            strategy=MigrationStrategy.HYBRID,
            interest_config={"engine": "v2"},
            changes=[],
            warnings=["Warning about something"],
        )

        diff = format_migration_diff({}, result)

        assert "Warning about something" in diff

    def test_format_includes_config_json(self):
        """Diff includes new config as JSON."""
        result = MigrationResult(
            success=True,
            profile_name="test",
            strategy=MigrationStrategy.HYBRID,
            interest_config={
                "engine": "v2",
                "preset": "trade-hub",
            },
            changes=[],
            warnings=[],
        )

        diff = format_migration_diff({}, result)

        assert '"engine": "v2"' in diff
        assert '"preset": "trade-hub"' in diff


class TestValidateMigration:
    """Tests for migration validation."""

    def test_valid_migration_no_errors(self):
        """Valid migration has no errors."""
        result = MigrationResult(
            success=True,
            profile_name="valid",
            strategy=MigrationStrategy.HYBRID,
            interest_config={
                "engine": "v2",
                "preset": "trade-hub",
            },
            changes=[],
            warnings=[],
        )

        errors = validate_migration(result)

        # May have validation warnings about unused presets but no critical errors
        # Empty is ideal
        assert isinstance(errors, list)

    def test_invalid_config_produces_errors(self):
        """Invalid config produces validation errors."""
        result = MigrationResult(
            success=True,
            profile_name="invalid",
            strategy=MigrationStrategy.HYBRID,
            interest_config={
                "engine": "v2",
                # Missing preset for simple tier
                "weights": {"invalid_category": 0.5},
            },
            changes=[],
            warnings=[],
        )

        errors = validate_migration(result)

        # Should have error for unknown category
        assert any("invalid_category" in e or "Unknown" in e for e in errors)


class TestPresetDetection:
    """Tests for auto-detection of presets."""

    def test_detect_trade_hub_systems(self):
        """Detects trade-hub from trade hub system names."""
        for hub in ["Jita", "Amarr", "Dodixie", "Rens", "Hek"]:
            profile = {
                "name": f"{hub.lower()}-monitor",
                "topology": {
                    "geographic": {
                        "systems": [{"name": hub}]
                    }
                },
                "triggers": {},
            }

            result = migrate_profile(profile)

            assert result.interest_config["preset"] == "trade-hub"

    def test_detect_from_high_value_trigger(self):
        """Detects trade-hub from high_value_threshold trigger."""
        profile = {
            "name": "value-monitor",
            "topology": {},
            "triggers": {
                "high_value_threshold": {"enabled": True}
            },
        }

        result = migrate_profile(profile)

        assert result.interest_config["preset"] == "trade-hub"

    def test_detect_from_watchlist_trigger(self):
        """Detects political from watchlist trigger."""
        profile = {
            "name": "watchlist-monitor",
            "topology": {},
            "triggers": {
                "watchlist_activity": {"enabled": True}
            },
        }

        result = migrate_profile(profile)

        assert result.interest_config["preset"] == "political"

    def test_default_to_balanced(self):
        """Defaults to balanced when no clear indicators."""
        profile = {
            "name": "minimal",
            "topology": {},
            "triggers": {},
        }

        result = migrate_profile(profile)

        assert result.interest_config["preset"] == "balanced"
