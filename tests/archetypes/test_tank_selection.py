"""
Tests for tank variant selection constraints and fallbacks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aria_esi.archetypes.tank_selection import (
    TankSelectionResult,
    TankVariantConfig,
    _map_path_to_variant,
    _resolve_default_variant,
    _variant_to_path,
    calculate_tank_score,
    discover_tank_variants,
    get_meta_yaml_path,
    load_tank_variant_config,
    resolve_skill_name_to_id,
    resolve_skill_names_to_ids,
    select_tank_variant,
)


class TestDataModels:
    def test_from_yaml_uses_defaults_when_keys_missing(self) -> None:
        config = TankVariantConfig.from_yaml({})

        assert config.available == []
        assert config.default == "armor_active"
        assert config.selection_strategy == "skill_based"
        assert config.skill_comparison == {}
        assert config.tie_breaker == "armor"

    def test_from_yaml_reads_explicit_values(self) -> None:
        config = TankVariantConfig.from_yaml(
            {
                "tank_variants": {
                    "available": ["shield_buffer", "armor_active"],
                    "default": "shield_buffer",
                    "selection_strategy": "default",
                },
                "skill_comparison": {
                    "armor": {"skills": ["Hull Upgrades"], "weight": 1.2},
                    "tie_breaker": "shield",
                },
            }
        )

        assert config.available == ["shield_buffer", "armor_active"]
        assert config.default == "shield_buffer"
        assert config.selection_strategy == "default"
        assert config.tie_breaker == "shield"
        assert config.skill_comparison["armor"]["skills"] == ["Hull Upgrades"]

    def test_selection_result_to_dict(self) -> None:
        result = TankSelectionResult(
            variant="shield_buffer",
            variant_path="shield",
            armor_score=2.0,
            shield_score=5.0,
            selection_reason="shield_skills_higher",
            skill_details={"shield": {"Shield Management": 5}},
        )

        assert result.to_dict() == {
            "variant": "shield_buffer",
            "variant_path": "shield",
            "armor_score": 2.0,
            "shield_score": 5.0,
            "selection_reason": "shield_skills_higher",
            "skill_details": {"shield": {"Shield Management": 5}},
        }


class TestSkillResolution:
    def test_resolve_skill_name_to_id_uses_builtin_mapping(self) -> None:
        assert resolve_skill_name_to_id("Hull Upgrades") == 3393

    def test_resolve_skill_name_to_id_returns_none_when_unresolvable(self) -> None:
        assert resolve_skill_name_to_id("Definitely Not A Real Skill Name") is None

    def test_resolve_skill_names_to_ids_filters_unresolved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mapping = {"A": 10, "B": None, "C": 30}
        monkeypatch.setattr(
            "aria_esi.archetypes.tank_selection.resolve_skill_name_to_id",
            lambda name: mapping[name],
        )

        resolved = resolve_skill_names_to_ids(["A", "B", "C"])

        assert resolved == {"A": 10, "C": 30}

    def test_calculate_tank_score_uses_weight_and_defaults_to_zero_for_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mapping = {"A": 100, "B": 200, "Missing": None}
        monkeypatch.setattr(
            "aria_esi.archetypes.tank_selection.resolve_skill_name_to_id",
            lambda name: mapping[name],
        )

        score, levels = calculate_tank_score(
            ["A", "B", "Missing"], {100: 4, 200: 2}, weight=1.5
        )

        assert score == pytest.approx(9.0)
        assert levels == {"A": 4, "B": 2, "Missing": 0}


class TestLoadConfig:
    def test_load_tank_variant_config_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert load_tank_variant_config(tmp_path / "meta.yaml") is None

    def test_load_tank_variant_config_handles_yaml_load_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        meta_path = tmp_path / "meta.yaml"
        meta_path.write_text("bad: [", encoding="utf-8")
        monkeypatch.setattr(
            "aria_esi.archetypes.tank_selection.load_yaml_file",
            lambda _: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        assert load_tank_variant_config(meta_path) is None

    def test_load_tank_variant_config_returns_none_for_empty_variants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        meta_path = tmp_path / "meta.yaml"
        meta_path.write_text("x: y", encoding="utf-8")
        monkeypatch.setattr(
            "aria_esi.archetypes.tank_selection.load_yaml_file",
            lambda _: {"tank_variants": {"available": []}},
        )

        assert load_tank_variant_config(meta_path) is None

    def test_load_tank_variant_config_returns_parsed_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        meta_path = tmp_path / "meta.yaml"
        meta_path.write_text("x: y", encoding="utf-8")
        monkeypatch.setattr(
            "aria_esi.archetypes.tank_selection.load_yaml_file",
            lambda _: {
                "tank_variants": {"available": ["armor_active"], "default": "armor_active"},
                "skill_comparison": {"tie_breaker": "armor"},
            },
        )

        config = load_tank_variant_config(meta_path)

        assert config is not None
        assert config.available == ["armor_active"]
        assert config.default == "armor_active"
        assert config.tie_breaker == "armor"


class TestSelectTankVariant:
    """Tests for select_tank_variant."""

    def test_single_variant_ignores_shield_heavy_skills(self) -> None:
        """Single-variant configs should never select an unavailable shield path."""
        config = TankVariantConfig(
            available=["armor_active"],
            default="armor_active",
            selection_strategy="skill_based",
            skill_comparison={
                "armor": {
                    "skills": [
                        "Hull Upgrades",
                        "Mechanics",
                        "Repair Systems",
                        "Armor Rigging",
                    ],
                    "weight": 1.0,
                },
                "shield": {
                    "skills": [
                        "Shield Management",
                        "Shield Operation",
                        "Shield Upgrades",
                        "Tactical Shield Manipulation",
                    ],
                    "weight": 1.0,
                },
                "tie_breaker": "armor",
            },
            tie_breaker="armor",
        )
        # Shield-heavy pilot profile.
        pilot_skills = {3416: 5, 3419: 5, 21059: 5, 3420: 5}

        result = select_tank_variant(config, pilot_skills)

        assert result.variant == "armor_active"
        assert result.variant_path == "armor"
        assert result.selection_reason == "single_variant"

    def test_override_selects_requested_available_variant(self) -> None:
        config = TankVariantConfig(
            available=["armor_active", "shield_buffer"],
            default="armor_active",
            selection_strategy="skill_based",
            tie_breaker="armor",
        )

        result = select_tank_variant(config, pilot_skills={}, override="shield")

        assert result.variant == "shield_buffer"
        assert result.variant_path == "shield"
        assert result.selection_reason == "override"

    def test_unavailable_override_falls_back_to_available_default(self) -> None:
        """Override to unavailable path should degrade to available variant."""
        config = TankVariantConfig(
            available=["armor_active"],
            default="armor_active",
            selection_strategy="skill_based",
            tie_breaker="armor",
        )

        result = select_tank_variant(config, pilot_skills={}, override="shield")

        assert result.variant == "armor_active"
        assert result.variant_path == "armor"
        assert result.selection_reason == "override_unavailable"

    def test_discovered_paths_constrain_selection(self) -> None:
        """Selection should honor discovered filesystem variant paths."""
        config = TankVariantConfig(
            available=["armor_active", "shield_buffer"],
            default="armor_active",
            selection_strategy="skill_based",
            skill_comparison={
                "armor": {"skills": ["Hull Upgrades"], "weight": 1.0},
                "shield": {"skills": ["Shield Management"], "weight": 1.0},
                "tie_breaker": "armor",
            },
            tie_breaker="armor",
        )
        # Shield-heavy pilot profile.
        pilot_skills = {3416: 5}

        result = select_tank_variant(
            config,
            pilot_skills,
            available_variant_paths=["armor"],
        )

        assert result.variant == "armor_active"
        assert result.variant_path == "armor"
        assert result.selection_reason == "single_variant"

    def test_non_skill_strategy_uses_default(self) -> None:
        config = TankVariantConfig(
            available=["armor_active", "shield_buffer"],
            default="shield_buffer",
            selection_strategy="default",
            tie_breaker="armor",
        )

        result = select_tank_variant(config, pilot_skills={3416: 5, 3393: 1})

        assert result.variant == "shield_buffer"
        assert result.variant_path == "shield"
        assert result.selection_reason == "default"

    def test_skill_strategy_picks_shield_when_score_higher(self) -> None:
        config = TankVariantConfig(
            available=["armor_active", "shield_buffer"],
            default="armor_active",
            selection_strategy="skill_based",
            skill_comparison={
                "armor": {"skills": ["Hull Upgrades"], "weight": 1.0},
                "shield": {"skills": ["Shield Management"], "weight": 1.0},
                "tie_breaker": "armor",
            },
            tie_breaker="armor",
        )

        result = select_tank_variant(config, pilot_skills={3393: 1, 3416: 5})

        assert result.variant_path == "shield"
        assert result.selection_reason == "shield_skills_higher"
        assert result.armor_score == pytest.approx(1.0)
        assert result.shield_score == pytest.approx(5.0)

    def test_tie_breaker_falls_back_to_default_when_unavailable(self) -> None:
        config = TankVariantConfig(
            available=["armor_active", "shield_buffer"],
            default="armor_active",
            selection_strategy="skill_based",
            skill_comparison={
                "armor": {"skills": ["Hull Upgrades"], "weight": 1.0},
                "shield": {"skills": ["Shield Management"], "weight": 1.0},
                "tie_breaker": "shield",
            },
            tie_breaker="invalid_path",
        )

        result = select_tank_variant(config, pilot_skills={3393: 3, 3416: 3})

        assert result.variant_path == "armor"
        assert result.selection_reason == "tie_breaker"

    def test_discovered_paths_fallback_to_paths_when_variants_do_not_map(self) -> None:
        config = TankVariantConfig(
            available=["buffer", "active"],
            default="armor_active",
            selection_strategy="skill_based",
            tie_breaker="armor",
        )

        result = select_tank_variant(
            config,
            pilot_skills={3416: 5},
            available_variant_paths=["shield"],
        )

        assert result.variant == "shield"
        assert result.variant_path == "shield"
        assert result.selection_reason == "single_variant"


class TestInternalHelpers:
    def test_variant_path_mapping_helpers(self) -> None:
        assert _variant_to_path("shield_buffer") == "shield"
        assert _variant_to_path("armor") == "armor"

        assert _map_path_to_variant("shield", ["armor_active", "shield_buffer"]) == "shield_buffer"
        assert _map_path_to_variant("shield", [], default_variant=None) == "shield"
        assert (
            _map_path_to_variant("shield", ["armor_active"], default_variant="armor_active")
            == "armor_active"
        )

    def test_resolve_default_variant(self) -> None:
        assert (
            _resolve_default_variant("armor_active", ["armor_active", "shield_buffer"])
            == "armor_active"
        )
        assert (
            _resolve_default_variant("armor", ["armor_active", "shield_buffer"])
            == "armor_active"
        )
        assert _resolve_default_variant("armor", []) == "armor"


class TestDiscovery:
    def test_discover_tank_variants_handles_missing_or_short_paths(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "aria_esi.archetypes.tank_selection.find_hull_directory",
            lambda _: None,
        )
        assert discover_tank_variants("too/short") == []
        assert discover_tank_variants("vexor/pve/missions/l3") == []

    def test_discover_tank_variants_reads_filesystem(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hull_dir = tmp_path / "vexor"
        base = hull_dir / "pve" / "missions" / "l3"
        (base / "shield").mkdir(parents=True)
        (base / "armor").mkdir(parents=True)
        (base / "not-a-variant").mkdir(parents=True)

        monkeypatch.setattr(
            "aria_esi.archetypes.tank_selection.find_hull_directory",
            lambda _: hull_dir,
        )

        assert discover_tank_variants("vexor/pve/missions/l3") == ["armor", "shield"]

    def test_get_meta_yaml_path_returns_none_for_missing_inputs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "aria_esi.archetypes.tank_selection.find_hull_directory",
            lambda _: None,
        )
        assert get_meta_yaml_path("too/short") is None
        assert get_meta_yaml_path("vexor/pve/missions/l3") is None

    def test_get_meta_yaml_path_returns_existing_meta(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hull_dir = tmp_path / "vexor"
        base = hull_dir / "pve" / "missions" / "l3"
        base.mkdir(parents=True)
        meta_path = base / "meta.yaml"
        meta_path.write_text("key: value", encoding="utf-8")

        monkeypatch.setattr(
            "aria_esi.archetypes.tank_selection.find_hull_directory",
            lambda _: hull_dir,
        )

        discovered = get_meta_yaml_path("vexor/pve/missions/l3")
        assert discovered == meta_path
