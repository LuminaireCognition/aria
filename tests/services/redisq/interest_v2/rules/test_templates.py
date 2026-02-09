"""
Tests for template-based custom rules module.

Tests the template registry, rule provider classes, and factory function.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from aria_esi.services.redisq.interest_v2.rules.templates import (
    TEMPLATE_REGISTRY,
    AttackerCountRule,
    SecurityBandRule,
    SoloKillRule,
    SystemMatchRule,
    TemplateSpec,
    ValueAboveRule,
    ValueBelowRule,
    create_template_rule,
    get_template_prefetch_capability,
    get_template_spec,
    list_templates,
    validate_template_params,
)


@dataclass
class MockProcessedKill:
    """Mock ProcessedKill for testing rule evaluation."""

    kill_id: int = 12345678
    solar_system_id: int = 30000142  # Jita
    victim_ship_type_id: int | None = 24690  # Vexor
    victim_corporation_id: int | None = 98000001
    victim_alliance_id: int | None = 99001234
    is_pod_kill: bool = False
    attacker_count: int = 3
    attacker_corps: list[int] = field(default_factory=lambda: [98000002, 98000003])
    attacker_alliances: list[int] = field(default_factory=lambda: [99005678])
    attacker_ship_types: list[int] = field(default_factory=lambda: [17703, 17703])
    final_blow_ship_type_id: int | None = 17703
    total_value: float = 150_000_000.0  # 150M ISK


class TestTemplateSpec:
    """Tests for TemplateSpec dataclass."""

    def test_create_template_spec(self) -> None:
        """Test creating a TemplateSpec."""
        spec = TemplateSpec(
            name="test",
            description="Test template",
            required_params=["param1"],
            optional_params=["param2"],
            prefetch_capable=True,
        )
        assert spec.name == "test"
        assert spec.description == "Test template"
        assert spec.required_params == ["param1"]
        assert spec.optional_params == ["param2"]
        assert spec.prefetch_capable is True

    def test_template_spec_partial_prefetch(self) -> None:
        """Test TemplateSpec with partial prefetch capability."""
        spec = TemplateSpec(
            name="partial",
            description="Partial prefetch",
            required_params=[],
            optional_params=[],
            prefetch_capable="victim",
        )
        assert spec.prefetch_capable == "victim"


class TestTemplateRegistry:
    """Tests for the template registry."""

    def test_registry_contains_expected_templates(self) -> None:
        """Test registry contains all expected templates."""
        expected = {
            "group_role",
            "category_match",
            "category_score",
            "value_above",
            "value_below",
            "ship_class",
            "ship_group",
            "security_band",
            "system_match",
            "attacker_count",
            "solo_kill",
        }
        assert set(TEMPLATE_REGISTRY.keys()) == expected

    def test_all_templates_have_specs(self) -> None:
        """Test all registry entries are TemplateSpec instances."""
        for name, spec in TEMPLATE_REGISTRY.items():
            assert isinstance(spec, TemplateSpec), f"{name} is not a TemplateSpec"

    @pytest.mark.parametrize(
        "template_name",
        ["value_above", "value_below", "ship_class", "ship_group", "security_band", "system_match"],
    )
    def test_prefetch_capable_templates(self, template_name: str) -> None:
        """Test templates marked as prefetch-capable."""
        spec = TEMPLATE_REGISTRY[template_name]
        assert spec.prefetch_capable is True

    @pytest.mark.parametrize(
        "template_name",
        ["attacker_count", "solo_kill", "category_match", "category_score"],
    )
    def test_non_prefetch_templates(self, template_name: str) -> None:
        """Test templates marked as non-prefetch-capable."""
        spec = TEMPLATE_REGISTRY[template_name]
        assert spec.prefetch_capable is False

    def test_group_role_partial_prefetch(self) -> None:
        """Test group_role has partial prefetch capability."""
        spec = TEMPLATE_REGISTRY["group_role"]
        assert spec.prefetch_capable == "victim"


class TestGetTemplateSpec:
    """Tests for get_template_spec function."""

    def test_get_existing_template(self) -> None:
        """Test retrieving existing template spec."""
        spec = get_template_spec("value_above")
        assert spec is not None
        assert spec.name == "value_above"

    def test_get_nonexistent_template(self) -> None:
        """Test retrieving nonexistent template returns None."""
        spec = get_template_spec("nonexistent")
        assert spec is None

    def test_get_returns_correct_type(self) -> None:
        """Test get returns TemplateSpec instance."""
        spec = get_template_spec("solo_kill")
        assert isinstance(spec, TemplateSpec)


class TestListTemplates:
    """Tests for list_templates function."""

    def test_list_returns_all_templates(self) -> None:
        """Test list returns all template names."""
        names = list_templates()
        assert len(names) == len(TEMPLATE_REGISTRY)
        assert set(names) == set(TEMPLATE_REGISTRY.keys())

    def test_list_returns_list_type(self) -> None:
        """Test list returns a list."""
        names = list_templates()
        assert isinstance(names, list)


class TestValueAboveRule:
    """Tests for ValueAboveRule class."""

    def test_create_rule(self) -> None:
        """Test creating ValueAboveRule."""
        rule = ValueAboveRule({"min": 100_000_000})
        assert rule._name == "value_above"
        assert rule._prefetch_capable is True
        assert rule._min == 100_000_000

    def test_default_min(self) -> None:
        """Test default min value is 0."""
        rule = ValueAboveRule({})
        assert rule._min == 0

    def test_evaluate_matches_above(self) -> None:
        """Test rule matches when value is above threshold."""
        rule = ValueAboveRule({"min": 100_000_000})
        kill = MockProcessedKill(total_value=150_000_000)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True
        assert result.rule_id == "value_above"
        assert "150,000,000" in result.reason
        assert ">=" in result.reason

    def test_evaluate_matches_equal(self) -> None:
        """Test rule matches when value equals threshold."""
        rule = ValueAboveRule({"min": 150_000_000})
        kill = MockProcessedKill(total_value=150_000_000)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True

    def test_evaluate_no_match_below(self) -> None:
        """Test rule does not match when value is below threshold."""
        rule = ValueAboveRule({"min": 200_000_000})
        kill = MockProcessedKill(total_value=150_000_000)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert "<" in result.reason

    def test_evaluate_no_kill(self) -> None:
        """Test rule handles None kill."""
        rule = ValueAboveRule({"min": 100_000_000})
        result = rule.evaluate(None, 30000142, {})
        assert result.matched is False
        assert result.reason == "No kill data"
        assert result.prefetch_capable is True

    def test_validate_valid(self) -> None:
        """Test validation with valid min."""
        rule = ValueAboveRule({"min": 100_000_000})
        errors = rule.validate({})
        assert errors == []

    def test_validate_negative_min(self) -> None:
        """Test validation rejects negative min."""
        rule = ValueAboveRule({"min": -100})
        errors = rule.validate({})
        assert len(errors) == 1
        assert "non-negative" in errors[0]


class TestValueBelowRule:
    """Tests for ValueBelowRule class."""

    def test_create_rule(self) -> None:
        """Test creating ValueBelowRule."""
        rule = ValueBelowRule({"max": 50_000_000})
        assert rule._name == "value_below"
        assert rule._prefetch_capable is True
        assert rule._max == 50_000_000

    def test_default_max(self) -> None:
        """Test default max value is infinity."""
        rule = ValueBelowRule({})
        assert rule._max == float("inf")

    def test_evaluate_matches_below(self) -> None:
        """Test rule matches when value is below threshold."""
        rule = ValueBelowRule({"max": 200_000_000})
        kill = MockProcessedKill(total_value=150_000_000)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True
        assert result.rule_id == "value_below"
        assert "<" in result.reason

    def test_evaluate_no_match_above(self) -> None:
        """Test rule does not match when value is above threshold."""
        rule = ValueBelowRule({"max": 100_000_000})
        kill = MockProcessedKill(total_value=150_000_000)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert ">=" in result.reason

    def test_evaluate_no_match_equal(self) -> None:
        """Test rule does not match when value equals threshold."""
        rule = ValueBelowRule({"max": 150_000_000})
        kill = MockProcessedKill(total_value=150_000_000)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False

    def test_evaluate_no_kill(self) -> None:
        """Test rule handles None kill."""
        rule = ValueBelowRule({"max": 100_000_000})
        result = rule.evaluate(None, 30000142, {})
        assert result.matched is False
        assert result.reason == "No kill data"


class TestSoloKillRule:
    """Tests for SoloKillRule class."""

    def test_create_rule(self) -> None:
        """Test creating SoloKillRule."""
        rule = SoloKillRule()
        assert rule._name == "solo_kill"
        assert rule._prefetch_capable is False

    def test_create_with_params(self) -> None:
        """Test SoloKillRule ignores params."""
        rule = SoloKillRule({"ignored": "value"})
        assert rule._name == "solo_kill"

    def test_evaluate_matches_solo(self) -> None:
        """Test rule matches when single attacker."""
        rule = SoloKillRule()
        kill = MockProcessedKill(attacker_count=1)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True
        assert "Solo kill" in result.reason
        assert "1 attacker" in result.reason

    def test_evaluate_no_match_multiple(self) -> None:
        """Test rule does not match with multiple attackers."""
        rule = SoloKillRule()
        kill = MockProcessedKill(attacker_count=3)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert "Not solo" in result.reason
        assert "3 attackers" in result.reason

    def test_evaluate_no_match_zero(self) -> None:
        """Test rule does not match with zero attackers."""
        rule = SoloKillRule()
        kill = MockProcessedKill(attacker_count=0)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False

    def test_evaluate_no_kill(self) -> None:
        """Test rule handles None kill."""
        rule = SoloKillRule()
        result = rule.evaluate(None, 30000142, {})
        assert result.matched is False
        assert result.prefetch_capable is False


class TestAttackerCountRule:
    """Tests for AttackerCountRule class."""

    def test_create_rule(self) -> None:
        """Test creating AttackerCountRule."""
        rule = AttackerCountRule({"min": 5, "max": 10})
        assert rule._name == "attacker_count"
        assert rule._prefetch_capable is False
        assert rule._min == 5
        assert rule._max == 10

    def test_default_values(self) -> None:
        """Test default min and max values."""
        rule = AttackerCountRule({})
        assert rule._min == 0
        assert rule._max == float("inf")

    def test_evaluate_matches_in_range(self) -> None:
        """Test rule matches when count in range."""
        rule = AttackerCountRule({"min": 2, "max": 5})
        kill = MockProcessedKill(attacker_count=3)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True
        assert "in range" in result.reason
        assert "[2, 5]" in result.reason

    def test_evaluate_matches_at_min(self) -> None:
        """Test rule matches when count equals min."""
        rule = AttackerCountRule({"min": 3, "max": 10})
        kill = MockProcessedKill(attacker_count=3)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True

    def test_evaluate_matches_at_max(self) -> None:
        """Test rule matches when count equals max."""
        rule = AttackerCountRule({"min": 1, "max": 3})
        kill = MockProcessedKill(attacker_count=3)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True

    def test_evaluate_no_match_below(self) -> None:
        """Test rule does not match when count below min."""
        rule = AttackerCountRule({"min": 5, "max": 10})
        kill = MockProcessedKill(attacker_count=3)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False
        assert "outside range" in result.reason

    def test_evaluate_no_match_above(self) -> None:
        """Test rule does not match when count above max."""
        rule = AttackerCountRule({"min": 1, "max": 2})
        kill = MockProcessedKill(attacker_count=3)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is False

    def test_evaluate_min_only(self) -> None:
        """Test rule with only min specified."""
        rule = AttackerCountRule({"min": 10})
        kill = MockProcessedKill(attacker_count=15)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True

    def test_evaluate_max_only(self) -> None:
        """Test rule with only max specified."""
        rule = AttackerCountRule({"max": 5})
        kill = MockProcessedKill(attacker_count=3)

        result = rule.evaluate(kill, 30000142, {})
        assert result.matched is True

    def test_evaluate_no_kill(self) -> None:
        """Test rule handles None kill."""
        rule = AttackerCountRule({"min": 1, "max": 5})
        result = rule.evaluate(None, 30000142, {})
        assert result.matched is False
        assert result.prefetch_capable is False


class TestSystemMatchRule:
    """Tests for SystemMatchRule class."""

    def test_create_rule_with_ids(self) -> None:
        """Test creating rule with system IDs."""
        rule = SystemMatchRule({"systems": [30000142, 30000144]})
        assert rule._name == "system_match"
        assert rule._prefetch_capable is True
        assert 30000142 in rule._system_ids
        assert 30000144 in rule._system_ids

    def test_create_rule_with_names(self) -> None:
        """Test creating rule with system names."""
        rule = SystemMatchRule({"systems": ["Jita", "Amarr"]})
        assert "jita" in rule._system_names
        assert "amarr" in rule._system_names

    def test_create_rule_mixed(self) -> None:
        """Test creating rule with mixed IDs and names."""
        rule = SystemMatchRule({"systems": [30000142, "Amarr"]})
        assert 30000142 in rule._system_ids
        assert "amarr" in rule._system_names

    def test_evaluate_matches_by_id(self) -> None:
        """Test rule matches by system ID."""
        rule = SystemMatchRule({"systems": [30000142, 30000144]})
        result = rule.evaluate(None, 30000142, {})
        assert result.matched is True
        assert "30000142" in result.reason
        assert "in match list" in result.reason

    def test_evaluate_matches_by_name(self) -> None:
        """Test rule matches by system name from config."""
        rule = SystemMatchRule({"systems": ["Jita"]})
        result = rule.evaluate(None, 99999, {"system_name": "Jita"})
        assert result.matched is True
        assert "jita" in result.reason.lower()

    def test_evaluate_name_case_insensitive(self) -> None:
        """Test name matching is case-insensitive."""
        rule = SystemMatchRule({"systems": ["JITA"]})
        result = rule.evaluate(None, 99999, {"system_name": "jita"})
        assert result.matched is True

    def test_evaluate_no_match(self) -> None:
        """Test rule does not match unregistered system."""
        rule = SystemMatchRule({"systems": [30000142]})
        result = rule.evaluate(None, 30000999, {})
        assert result.matched is False
        assert "not in match list" in result.reason

    def test_evaluate_empty_systems(self) -> None:
        """Test rule with empty systems list."""
        rule = SystemMatchRule({"systems": []})
        result = rule.evaluate(None, 30000142, {})
        assert result.matched is False


class TestSecurityBandRule:
    """Tests for SecurityBandRule class."""

    def test_create_rule(self) -> None:
        """Test creating SecurityBandRule."""
        rule = SecurityBandRule({"bands": ["high", "low"]})
        assert rule._name == "security_band"
        assert rule._prefetch_capable is True
        assert "high" in rule._bands
        assert "low" in rule._bands

    def test_bands_case_insensitive(self) -> None:
        """Test band names are lowercased."""
        rule = SecurityBandRule({"bands": ["HIGH", "Low"]})
        assert "high" in rule._bands
        assert "low" in rule._bands

    def test_evaluate_highsec_matches(self) -> None:
        """Test rule matches highsec (>= 0.5)."""
        rule = SecurityBandRule({"bands": ["high"]})
        result = rule.evaluate(None, 30000142, {"security_status": 0.95})
        assert result.matched is True
        assert "high" in result.reason.lower()

    def test_evaluate_lowsec_matches(self) -> None:
        """Test rule matches lowsec (0.0 < sec < 0.5)."""
        rule = SecurityBandRule({"bands": ["low"]})
        result = rule.evaluate(None, 30000142, {"security_status": 0.3})
        assert result.matched is True
        assert "low" in result.reason.lower()

    def test_evaluate_nullsec_matches(self) -> None:
        """Test rule matches nullsec (0.0 to -0.5)."""
        rule = SecurityBandRule({"bands": ["null"]})
        result = rule.evaluate(None, 30000142, {"security_status": -0.2})
        assert result.matched is True
        assert "null" in result.reason.lower()

    def test_evaluate_wormhole_matches(self) -> None:
        """Test rule matches wormhole (<= -0.5)."""
        rule = SecurityBandRule({"bands": ["wh"]})
        result = rule.evaluate(None, 30000142, {"security_status": -1.0})
        assert result.matched is True
        assert "wh" in result.reason.lower()

    def test_evaluate_border_highsec(self) -> None:
        """Test exactly 0.5 is highsec."""
        rule = SecurityBandRule({"bands": ["high"]})
        result = rule.evaluate(None, 30000142, {"security_status": 0.5})
        assert result.matched is True

    def test_evaluate_border_lowsec_upper(self) -> None:
        """Test 0.49 is lowsec."""
        rule = SecurityBandRule({"bands": ["low"]})
        result = rule.evaluate(None, 30000142, {"security_status": 0.49})
        assert result.matched is True

    def test_evaluate_border_lowsec_lower(self) -> None:
        """Test 0.01 is lowsec."""
        rule = SecurityBandRule({"bands": ["low"]})
        result = rule.evaluate(None, 30000142, {"security_status": 0.01})
        assert result.matched is True

    def test_evaluate_border_null(self) -> None:
        """Test exactly 0.0 is null."""
        rule = SecurityBandRule({"bands": ["null"]})
        result = rule.evaluate(None, 30000142, {"security_status": 0.0})
        assert result.matched is True

    def test_evaluate_no_match(self) -> None:
        """Test rule does not match wrong band."""
        rule = SecurityBandRule({"bands": ["high"]})
        result = rule.evaluate(None, 30000142, {"security_status": 0.3})
        assert result.matched is False
        assert "'low'" in result.reason
        assert "not in" in result.reason

    def test_evaluate_default_security(self) -> None:
        """Test rule uses default 0.5 security if not in config."""
        rule = SecurityBandRule({"bands": ["high"]})
        result = rule.evaluate(None, 30000142, {})
        assert result.matched is True  # 0.5 default is highsec


class TestCreateTemplateRule:
    """Tests for create_template_rule factory function."""

    def test_create_value_above(self) -> None:
        """Test factory creates ValueAboveRule."""
        rule = create_template_rule("value_above", {"min": 100})
        assert isinstance(rule, ValueAboveRule)

    def test_create_value_below(self) -> None:
        """Test factory creates ValueBelowRule."""
        rule = create_template_rule("value_below", {"max": 100})
        assert isinstance(rule, ValueBelowRule)

    def test_create_solo_kill(self) -> None:
        """Test factory creates SoloKillRule."""
        rule = create_template_rule("solo_kill", {})
        assert isinstance(rule, SoloKillRule)

    def test_create_attacker_count(self) -> None:
        """Test factory creates AttackerCountRule."""
        rule = create_template_rule("attacker_count", {"min": 5})
        assert isinstance(rule, AttackerCountRule)

    def test_create_system_match(self) -> None:
        """Test factory creates SystemMatchRule."""
        rule = create_template_rule("system_match", {"systems": [1, 2]})
        assert isinstance(rule, SystemMatchRule)

    def test_create_security_band(self) -> None:
        """Test factory creates SecurityBandRule."""
        rule = create_template_rule("security_band", {"bands": ["high"]})
        assert isinstance(rule, SecurityBandRule)

    def test_create_unknown_template(self) -> None:
        """Test factory returns None for unknown template."""
        rule = create_template_rule("unknown_template", {})
        assert rule is None


class TestValidateTemplateParams:
    """Tests for validate_template_params function."""

    def test_validate_valid_params(self) -> None:
        """Test validation passes with valid params."""
        errors = validate_template_params("value_above", {"min": 100})
        assert errors == []

    def test_validate_missing_required(self) -> None:
        """Test validation fails for missing required param."""
        errors = validate_template_params("value_above", {})
        assert len(errors) == 1
        assert "requires parameter 'min'" in errors[0]

    def test_validate_unknown_template(self) -> None:
        """Test validation fails for unknown template."""
        errors = validate_template_params("unknown", {})
        assert len(errors) == 1
        assert "Unknown template" in errors[0]

    def test_validate_optional_params_ok(self) -> None:
        """Test validation passes without optional params."""
        # attacker_count has optional min/max
        errors = validate_template_params("attacker_count", {})
        assert errors == []

    def test_validate_solo_kill_no_params(self) -> None:
        """Test solo_kill requires no params."""
        errors = validate_template_params("solo_kill", {})
        assert errors == []


class TestGetTemplatePrefetchCapability:
    """Tests for get_template_prefetch_capability function."""

    def test_prefetch_capable_template(self) -> None:
        """Test returns True for prefetch-capable template."""
        result = get_template_prefetch_capability("value_above", {})
        assert result is True

    def test_non_prefetch_template(self) -> None:
        """Test returns False for non-prefetch template."""
        result = get_template_prefetch_capability("solo_kill", {})
        assert result is False

    def test_partial_prefetch_victim_role(self) -> None:
        """Test returns True for group_role with victim role."""
        result = get_template_prefetch_capability("group_role", {"role": "victim"})
        assert result is True

    def test_partial_prefetch_attacker_role(self) -> None:
        """Test returns False for group_role with attacker role."""
        result = get_template_prefetch_capability("group_role", {"role": "attacker"})
        assert result is False

    def test_partial_prefetch_any_role(self) -> None:
        """Test returns False for group_role with any role."""
        result = get_template_prefetch_capability("group_role", {"role": "any"})
        assert result is False

    def test_partial_prefetch_no_role(self) -> None:
        """Test returns False for group_role without role param."""
        result = get_template_prefetch_capability("group_role", {})
        assert result is False

    def test_unknown_template(self) -> None:
        """Test returns False for unknown template."""
        result = get_template_prefetch_capability("unknown", {})
        assert result is False
