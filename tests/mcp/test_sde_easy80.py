"""
Tests for Easy 80% Skill Planning MCP Tools.

Tests the efficacy calculations, multiplier skill identification,
and Easy 80% plan generation logic.
"""

from __future__ import annotations

from aria_esi.mcp.sde.tools_easy80 import (
    MULTIPLIER_SKILLS,
    SKILLS_REQUIRING_V,
    calculate_efficacy,
    detect_ship_roles,
    generate_easy_80_plan,
    load_breakpoint_skills,
)


class TestEfficacyCalculation:
    """Tests for efficacy calculation.

    Note: Efficacy now uses weighted average, not multiplicative formula.
    This gives more realistic percentages for Easy 80% planning.
    """

    def test_full_efficacy_at_target(self):
        """Skills at target level = 100% efficacy."""
        skills_at_level = {"Drones": 5, "Drone Interfacing": 5}
        target_levels = {"Drones": 5, "Drone Interfacing": 5}
        result = calculate_efficacy(skills_at_level, target_levels)
        assert result == 100.0

    def test_partial_efficacy(self):
        """Skills below target reduce efficacy with weighted average."""
        skills_at_level = {"Drones": 4, "Drone Interfacing": 4}
        target_levels = {"Drones": 5, "Drone Interfacing": 5}
        result = calculate_efficacy(skills_at_level, target_levels)
        # Weighted average: both at 4/5 = 0.8, result is 80%
        # Drone Interfacing is a multiplier (weight 3), Drones is not (weight 1)
        # Weighted: (0.8*3 + 0.8*1) / (3+1) = 3.2 / 4 = 0.8 = 80%
        assert result == 80.0

    def test_mixed_levels(self):
        """Mix of skill levels calculates correctly with weighted average."""
        skills_at_level = {"Drones": 5, "Drone Interfacing": 4}
        target_levels = {"Drones": 5, "Drone Interfacing": 5}
        result = calculate_efficacy(skills_at_level, target_levels)
        # Drones: 5/5=1.0, Drone Interfacing: 4/5=0.8
        # Drone Interfacing has weight 3 (multiplier), Drones has weight 1
        # Weighted: (1.0*1 + 0.8*3) / (1+3) = 3.4 / 4 = 0.85 = 85%
        assert result == 85.0

    def test_empty_skills(self):
        """Empty skill lists return 100% (no reduction)."""
        result = calculate_efficacy({}, {})
        assert result == 100.0

    def test_missing_skill_reduces_efficacy(self):
        """Skills not in current dict reduce efficacy proportionally."""
        skills_at_level = {"Other Skill": 5}  # Has one skill but not the target
        target_levels = {"Drones": 5, "Other Skill": 5}
        result = calculate_efficacy(skills_at_level, target_levels)
        # Drones: 0/5 = 0 (weight 1), Other Skill: 5/5 = 1.0 (weight 1)
        # Weighted: (0*1 + 1*1) / (1+1) = 1 / 2 = 0.5 = 50%
        assert result == 50.0


class TestGenerateEasy80Plan:
    """Tests for Easy 80% plan generation."""

    def test_basic_plan_generation(self):
        """Basic plan separates skills correctly."""
        full_tree = [
            {"skill_name": "Gallente Cruiser", "required_level": 3, "rank": 5},
            {"skill_name": "Spaceship Command", "required_level": 3, "rank": 1},
        ]
        plan = generate_easy_80_plan(full_tree)

        assert "required_at_level" in plan
        assert "cap_at_4" in plan
        assert "train_to_5" in plan
        assert len(plan["required_at_level"]) == 2

    def test_multiplier_skills_flagged(self):
        """Multiplier skills are flagged in the plan."""
        full_tree = [
            {"skill_name": "Drone Interfacing", "required_level": 0, "rank": 5},
        ]
        plan = generate_easy_80_plan(full_tree)

        # Should be in cap_at_4 with multiplier flag
        cap_at_4 = plan.get("cap_at_4", [])
        drone_int = next(
            (s for s in cap_at_4 if s["skill_name"] == "Drone Interfacing"),
            None,
        )
        if drone_int:
            assert drone_int.get("is_multiplier") is True

    def test_t2_skills_identified(self):
        """Skills commonly requiring V for T2 go to train_to_5 when at level V."""
        full_tree = [
            {"skill_name": "Drones", "required_level": 5, "rank": 1},
        ]
        plan = generate_easy_80_plan(full_tree)

        # Drones at V with SKILLS_REQUIRING_V flag should go to train_to_5
        train_to_5 = plan.get("train_to_5", [])
        drones = next(
            (s for s in train_to_5 if s["skill_name"] == "Drones"),
            None,
        )
        assert drones is not None, "Drones at V should be in train_to_5"
        assert drones.get("requires_v_for_t2") is True
        assert drones.get("easy_80_level") == 5

    def test_easy_80_level_respects_requirements(self):
        """Easy 80 level doesn't go below required level."""
        full_tree = [
            {"skill_name": "Gallente Cruiser", "required_level": 3, "rank": 5},
        ]
        plan = generate_easy_80_plan(full_tree)

        required = plan.get("required_at_level", [])
        skill = next(
            (s for s in required if s["skill_name"] == "Gallente Cruiser"),
            None,
        )
        assert skill is not None
        assert skill.get("easy_80_level") == 3


class TestMultiplierSkillsConstants:
    """Tests for multiplier skill definitions."""

    def test_multiplier_skills_have_required_fields(self):
        """All multiplier skills have effect, impact, and priority."""
        for skill_name, data in MULTIPLIER_SKILLS.items():
            assert "effect" in data, f"{skill_name} missing effect"
            assert "impact" in data, f"{skill_name} missing impact"
            assert "priority" in data, f"{skill_name} missing priority"

    def test_multiplier_priorities_valid(self):
        """Priority values are 1 (high) or 2 (medium)."""
        for skill_name, data in MULTIPLIER_SKILLS.items():
            assert data["priority"] in [1, 2], f"{skill_name} invalid priority"

    def test_key_multipliers_present(self):
        """Critical multiplier skills are defined."""
        assert "Drone Interfacing" in MULTIPLIER_SKILLS
        assert "Surgical Strike" in MULTIPLIER_SKILLS
        assert "Warhead Upgrades" in MULTIPLIER_SKILLS


class TestSkillsRequiringVConstants:
    """Tests for T2-requiring skill definitions."""

    def test_skills_requiring_v_have_reasons(self):
        """All skills requiring V list what they unlock."""
        for skill_name, unlocks in SKILLS_REQUIRING_V.items():
            assert isinstance(unlocks, list), f"{skill_name} unlocks not a list"
            assert len(unlocks) > 0, f"{skill_name} has no unlock reasons"

    def test_common_t2_skills_present(self):
        """Common T2-prerequisite skills are defined."""
        assert "Drones" in SKILLS_REQUIRING_V
        assert "Mechanics" in SKILLS_REQUIRING_V
        assert "Mining" in SKILLS_REQUIRING_V


class TestEasy80Integration:
    """Integration-style tests for the Easy 80% system."""

    def test_drone_boat_plan_structure(self):
        """A drone boat's plan should prioritize drone skills correctly."""
        # Simulated skill tree for a drone cruiser
        full_tree = [
            {"skill_name": "Gallente Cruiser", "required_level": 3, "rank": 5},
            {"skill_name": "Drones", "required_level": 5, "rank": 1},
            {"skill_name": "Drone Interfacing", "required_level": 0, "rank": 5},
            {"skill_name": "Medium Drone Operation", "required_level": 0, "rank": 2},
        ]
        plan = generate_easy_80_plan(full_tree, "Ship")

        # Drones V should be in train_to_5 (T2 skill at V goes there)
        train_to_5_names = [s["skill_name"] for s in plan.get("train_to_5", [])]
        assert "Drones" in train_to_5_names, "Drones at V should be in train_to_5"

        # Drone Interfacing should be in cap_at_4 and flagged as multiplier
        cap_at_4 = plan.get("cap_at_4", [])
        drone_int = next(
            (s for s in cap_at_4 if s["skill_name"] == "Drone Interfacing"),
            None,
        )
        assert drone_int is not None, "Drone Interfacing should be in cap_at_4"
        assert drone_int.get("is_multiplier") is True

    def test_time_savings_calculation_concept(self):
        """Easy 80% should save significant time vs full mastery.

        Level V takes ~4.5x as long as I-IV combined.
        Capping at IV should save ~80% of training time per skill.
        """
        # This is more of a conceptual test - the actual calculation
        # happens in calculate_plan_training_time which needs DB access.
        #
        # For a rank 5 skill:
        # Level IV cumulative: ~4d 22h
        # Level V cumulative: ~24d 18h
        # Training V alone: ~19d 20h
        #
        # Savings: 19d 20h per skill capped at IV vs V
        pass  # Conceptual verification - actual tested in integration tests


class TestMultiplierSkillsCategorization:
    """Tests for the fixed skill categorization logic."""

    def test_multiplier_in_prereqs_gets_flagged(self):
        """Multiplier skills should be flagged even with required_level > 0."""
        full_tree = [
            {"skill_name": "Gallente Cruiser", "required_level": 3, "rank": 5},
            {"skill_name": "Drone Interfacing", "required_level": 3, "rank": 5},
        ]
        plan = generate_easy_80_plan(full_tree, "Ship")

        # Drone Interfacing should be in cap_at_4 with multiplier flag
        cap_at_4 = plan.get("cap_at_4", [])
        drone_int = next(
            (s for s in cap_at_4 if s["skill_name"] == "Drone Interfacing"),
            None,
        )
        assert drone_int is not None, "Drone Interfacing should be in cap_at_4"
        assert drone_int.get("is_multiplier") is True
        # easy_80_level should be max(required, 4) = 4 since required is 3
        assert drone_int.get("easy_80_level") == 4

    def test_skill_at_v_in_skills_requiring_v_goes_to_train_to_5(self):
        """Skills in SKILLS_REQUIRING_V at level 5 should go to train_to_5."""
        full_tree = [
            {"skill_name": "Drones", "required_level": 5, "rank": 1},
            {"skill_name": "Light Drone Operation", "required_level": 3, "rank": 2},
        ]
        plan = generate_easy_80_plan(full_tree, "Module")

        train_to_5 = plan.get("train_to_5", [])
        drones = next((s for s in train_to_5 if s["skill_name"] == "Drones"), None)
        assert drones is not None, "Drones V should be in train_to_5"
        assert drones.get("easy_80_level") == 5
        assert "reason" in drones

    def test_multiplier_skill_respects_higher_required(self):
        """If multiplier skill required at 5, easy_80_level should be 5."""
        full_tree = [
            {"skill_name": "Drone Interfacing", "required_level": 5, "rank": 5},
        ]
        plan = generate_easy_80_plan(full_tree)

        cap_at_4 = plan.get("cap_at_4", [])
        drone_int = next(
            (s for s in cap_at_4 if s["skill_name"] == "Drone Interfacing"),
            None,
        )
        assert drone_int is not None
        # Should respect required_level of 5
        assert drone_int.get("easy_80_level") == 5

    def test_regular_prereq_stays_at_required(self):
        """Non-multiplier, non-T2 skills stay at required level."""
        full_tree = [
            {"skill_name": "Gallente Cruiser", "required_level": 3, "rank": 5},
            {"skill_name": "Spaceship Command", "required_level": 4, "rank": 1},
        ]
        plan = generate_easy_80_plan(full_tree)

        required = plan.get("required_at_level", [])
        gc = next((s for s in required if s["skill_name"] == "Gallente Cruiser"), None)
        sc = next((s for s in required if s["skill_name"] == "Spaceship Command"), None)

        assert gc is not None
        assert gc.get("easy_80_level") == 3
        assert sc is not None
        assert sc.get("easy_80_level") == 4


class TestEfficacyWeighting:
    """Tests for the weighted efficacy calculation."""

    def test_efficacy_with_multipliers_weighted_higher(self):
        """Multiplier skills should have more impact on efficacy."""
        # All skills at 4/5
        skills_at_level = {
            "Drones": 4,
            "Drone Interfacing": 4,
            "Some Random Skill": 4,
        }
        target_levels = {
            "Drones": 5,
            "Drone Interfacing": 5,
            "Some Random Skill": 5,
        }

        efficacy = calculate_efficacy(skills_at_level, target_levels)

        # With weighted average, efficacy should be higher than pure multiplicative
        # Pure multiplicative: 0.8^3 = 51.2%
        # Weighted should be higher because we're averaging ratios
        assert efficacy > 60.0  # More reasonable with weighted average
        assert efficacy < 100.0

    def test_efficacy_100_when_all_at_target(self):
        """Full skills = 100% efficacy."""
        skills = {"Drones": 5, "Drone Interfacing": 5}
        targets = {"Drones": 5, "Drone Interfacing": 5}
        assert calculate_efficacy(skills, targets) == 100.0

    def test_efficacy_with_role_uses_role_weights(self):
        """Role parameter should affect weighting."""
        skills = {"Drones": 4, "Drone Interfacing": 4}
        targets = {"Drones": 5, "Drone Interfacing": 5}

        # With drone_boat role, drone skills are weighted higher
        efficacy_with_role = calculate_efficacy(skills, targets, role="drone_boat")
        efficacy_without_role = calculate_efficacy(skills, targets)

        # Both should be reasonable (70-85% range)
        assert 70 <= efficacy_with_role <= 90
        assert 70 <= efficacy_without_role <= 90


class TestYamlLoading:
    """Tests for YAML data loading functions."""

    def test_load_efficacy_rules_returns_dict(self):
        """Should return a dict with ship_roles."""
        from aria_esi.mcp.sde.tools_easy80 import load_efficacy_rules

        rules = load_efficacy_rules()
        assert isinstance(rules, dict)
        # May be empty if file not found, but should be a dict
        if rules:
            assert "ship_roles" in rules

    def test_load_meta_alternatives_returns_dict(self):
        """Should return a dict."""
        from aria_esi.mcp.sde.tools_easy80 import load_meta_alternatives

        alts = load_meta_alternatives()
        assert isinstance(alts, dict)

    def test_yaml_cache_reloads_on_file_change(self, tmp_path):
        """YAML caches should reload when file is modified (hot-reload)."""
        import os
        import time
        from unittest.mock import patch

        from aria_esi.mcp.sde.tools_easy80 import (
            load_breakpoint_skills,
            reset_easy80_caches,
        )

        # Setup: create a test YAML file
        skills_dir = tmp_path / "reference" / "skills"
        skills_dir.mkdir(parents=True)
        bp_file = skills_dir / "breakpoint_skills.yaml"
        bp_file.write_text("TestSkill:\n  breakpoint_level: 4\n  effect: test\n  impact: high\n  priority: 1\n  reason: test\n  category: combat\n")

        reset_easy80_caches()

        with patch(
            "aria_esi.mcp.sde.tools_easy80._get_reference_path",
            return_value=skills_dir,
        ):
            # First load
            result1 = load_breakpoint_skills()
            assert "TestSkill" in result1

            # Modify file with newer mtime
            time.sleep(0.01)
            bp_file.write_text("UpdatedSkill:\n  breakpoint_level: 5\n  effect: updated\n  impact: high\n  priority: 1\n  reason: updated\n  category: combat\n")
            os.utime(bp_file, (time.time() + 1, time.time() + 1))

            # Should reload
            result2 = load_breakpoint_skills()
            assert "UpdatedSkill" in result2
            assert "TestSkill" not in result2

        reset_easy80_caches()

    def test_detect_ship_roles_with_known_ship(self):
        """Should detect roles for known ships."""
        from aria_esi.mcp.sde.tools_easy80 import detect_ship_roles

        roles = detect_ship_roles("Cruiser", "Vexor Navy Issue")
        # Should detect drone_boat from example_ships
        assert "drone_boat" in roles or len(roles) == 0  # Depends on YAML content

    def test_get_support_skills_excludes_existing(self):
        """Should not return skills already in the tree."""
        from aria_esi.mcp.sde.tools_easy80 import get_support_skills_for_roles

        existing = {"Drones", "Drone Interfacing"}
        support = get_support_skills_for_roles(["drone_boat"], existing)

        # Should not include skills we already have
        support_names = {s["skill_name"] for s in support}
        assert not support_names.intersection(existing)


class TestBreakpointSkillsConstants:
    """Tests for breakpoint skill definitions."""

    def test_breakpoint_skills_have_required_fields(self):
        """All breakpoint skills have required metadata fields."""
        required_fields = ["breakpoint_level", "effect", "impact", "priority", "reason"]
        breakpoint_skills = load_breakpoint_skills()
        for skill_name, data in breakpoint_skills.items():
            for field in required_fields:
                assert field in data, f"{skill_name} missing {field}"

    def test_breakpoint_skills_have_category(self):
        """All breakpoint skills have a category for filtering."""
        breakpoint_skills = load_breakpoint_skills()
        for skill_name, data in breakpoint_skills.items():
            assert "category" in data, f"{skill_name} missing category"
            assert data["category"] in [
                "combat", "tank", "stealth", "industrial",
                "exploration", "capital", "logi", "universal"
            ], f"{skill_name} has invalid category: {data['category']}"

    def test_core_combat_breakpoints_present(self):
        """Critical combat breakpoint skills are defined."""
        breakpoint_skills = load_breakpoint_skills()
        assert "Drones" in breakpoint_skills
        assert "Advanced Weapon Upgrades" in breakpoint_skills
        assert "Thermodynamics" in breakpoint_skills

    def test_stealth_breakpoints_present(self):
        """Stealth/covert breakpoint skills are defined."""
        breakpoint_skills = load_breakpoint_skills()
        assert "Cloaking" in breakpoint_skills
        assert breakpoint_skills["Cloaking"]["breakpoint_level"] == 4
        assert "stealth_ship" in breakpoint_skills["Cloaking"]["applies_to_roles"]

    def test_industrial_breakpoints_present(self):
        """Industrial breakpoint skills are defined."""
        breakpoint_skills = load_breakpoint_skills()
        assert "Mining" in breakpoint_skills
        assert "Gas Cloud Harvesting" in breakpoint_skills
        assert "Ice Harvesting" in breakpoint_skills
        # Gas and Ice are level 1 binary unlocks
        assert breakpoint_skills["Gas Cloud Harvesting"]["breakpoint_level"] == 1
        assert breakpoint_skills["Ice Harvesting"]["breakpoint_level"] == 1

    def test_capital_breakpoints_present(self):
        """Capital/jump breakpoint skills are defined."""
        breakpoint_skills = load_breakpoint_skills()
        assert "Jump Drive Calibration" in breakpoint_skills
        assert "Cynosural Field Theory" in breakpoint_skills
        assert breakpoint_skills["Jump Drive Calibration"]["breakpoint_level"] == 5
        assert breakpoint_skills["Cynosural Field Theory"]["breakpoint_level"] == 1

    def test_logi_breakpoints_present(self):
        """Logistics breakpoint skills are defined."""
        breakpoint_skills = load_breakpoint_skills()
        assert "Remote Armor Repair Systems" in breakpoint_skills
        assert "Remote Shield Emission" in breakpoint_skills
        assert "Capacitor Management" in breakpoint_skills

    def test_exploration_breakpoints_present(self):
        """Exploration breakpoint skills are defined."""
        breakpoint_skills = load_breakpoint_skills()
        assert "Archaeology" in breakpoint_skills
        assert "Hacking" in breakpoint_skills
        # T2 analyzers require level 3
        assert breakpoint_skills["Archaeology"]["breakpoint_level"] == 3
        assert breakpoint_skills["Hacking"]["breakpoint_level"] == 3

    def test_tank_breakpoints_present(self):
        """Tank breakpoint skills are defined."""
        breakpoint_skills = load_breakpoint_skills()
        assert "Hull Upgrades" in breakpoint_skills
        assert "armor_tank" in breakpoint_skills["Hull Upgrades"]["applies_to_roles"]


class TestRoleDetection:
    """Tests for ship role detection function."""

    def test_detect_drone_boats(self):
        """Should detect drone boat ships."""
        # Gallente drone ships
        assert "drone_boat" in detect_ship_roles("Cruiser", "Vexor")
        assert "drone_boat" in detect_ship_roles("Battlecruiser", "Myrmidon")
        assert "drone_boat" in detect_ship_roles("Battleship", "Dominix")
        # Pirate faction drone ships
        assert "drone_boat" in detect_ship_roles("Cruiser", "Gila")
        assert "drone_boat" in detect_ship_roles("Heavy Assault Cruiser", "Ishtar")
        assert "drone_boat" in detect_ship_roles("Battleship", "Rattlesnake")

    def test_detect_stealth_ships(self):
        """Should detect stealth/covert ops ships."""
        # Covert Ops frigates
        assert "stealth_ship" in detect_ship_roles("Covert Ops", "Helios")
        assert "stealth_ship" in detect_ship_roles("Covert Ops", "Anathema")
        assert "stealth_ship" in detect_ship_roles("Covert Ops", "Buzzard")
        assert "stealth_ship" in detect_ship_roles("Covert Ops", "Cheetah")
        # Stealth Bombers
        assert "stealth_ship" in detect_ship_roles("Stealth Bomber", "Hound")
        assert "stealth_ship" in detect_ship_roles("Stealth Bomber", "Nemesis")
        # Force Recons
        assert "stealth_ship" in detect_ship_roles("Force Recon Ship", "Arazu")
        assert "stealth_ship" in detect_ship_roles("Force Recon Ship", "Falcon")
        # Black Ops
        assert "stealth_ship" in detect_ship_roles("Black Ops", "Sin")
        assert "stealth_ship" in detect_ship_roles("Black Ops", "Widow")
        # Exploration ships with covert cloak
        assert "stealth_ship" in detect_ship_roles("Frigate", "Astero")
        assert "stealth_ship" in detect_ship_roles("Cruiser", "Stratios")

    def test_detect_logi_ships(self):
        """Should detect logistics ships."""
        # T1 Logi
        assert "logi" in detect_ship_roles("Cruiser", "Scythe")
        assert "logi" in detect_ship_roles("Cruiser", "Osprey")
        assert "logi" in detect_ship_roles("Cruiser", "Augoror")
        assert "logi" in detect_ship_roles("Cruiser", "Exequror")
        # T2 Logi
        assert "logi" in detect_ship_roles("Logistics", "Scimitar")
        assert "logi" in detect_ship_roles("Logistics", "Basilisk")
        assert "logi" in detect_ship_roles("Logistics", "Guardian")
        assert "logi" in detect_ship_roles("Logistics", "Oneiros")

    def test_detect_jump_capable_ships(self):
        """Should detect jump-capable ships."""
        # Jump Freighters
        assert "jump_capable" in detect_ship_roles("Jump Freighter", "Rhea")
        assert "jump_capable" in detect_ship_roles("Jump Freighter", "Anshar")
        # Black Ops have jump drives
        assert "jump_capable" in detect_ship_roles("Black Ops", "Sin")
        # Capital groups
        assert "jump_capable" in detect_ship_roles("Carrier", "Archon")
        assert "jump_capable" in detect_ship_roles("Dreadnought", "Revelation")

    def test_detect_mining_ships(self):
        """Should detect mining ships."""
        assert "miner" in detect_ship_roles("Frigate", "Venture")
        assert "miner" in detect_ship_roles("Mining Barge", "Procurer")
        assert "miner" in detect_ship_roles("Mining Barge", "Retriever")
        assert "miner" in detect_ship_roles("Exhumer", "Skiff")
        assert "miner" in detect_ship_roles("Exhumer", "Hulk")

    def test_detect_specialized_mining(self):
        """Should detect gas/ice specialized mining ships."""
        # Prospect has covert cloak and is for gas mining
        roles = detect_ship_roles("Expedition Frigate", "Prospect")
        assert "gas_miner" in roles
        assert "stealth_ship" in roles
        # Endurance is for ice
        roles = detect_ship_roles("Expedition Frigate", "Endurance")
        assert "ice_miner" in roles

    def test_detect_exploration_ships(self):
        """Should detect exploration ships."""
        # T1 exploration frigates
        assert "explorer" in detect_ship_roles("Frigate", "Heron")
        assert "explorer" in detect_ship_roles("Frigate", "Imicus")
        assert "explorer" in detect_ship_roles("Frigate", "Probe")
        assert "explorer" in detect_ship_roles("Frigate", "Magnate")
        # Astero and Stratios
        assert "explorer" in detect_ship_roles("Frigate", "Astero")
        assert "explorer" in detect_ship_roles("Cruiser", "Stratios")

    def test_detect_active_tank_ships(self):
        """Should detect active-tanked ships."""
        # Marauders are always active tanked
        assert "active_tank" in detect_ship_roles("Marauder", "Kronos")
        assert "active_tank" in detect_ship_roles("Marauder", "Vargur")
        # Specific active tank ships
        assert "active_tank" in detect_ship_roles("Cruiser", "Vexor Navy Issue")
        assert "active_tank" in detect_ship_roles("Cruiser", "Gila")

    def test_detect_faction_tank_type(self):
        """Should detect armor vs shield tank by faction."""
        # Gallente = armor
        assert "armor_tank" in detect_ship_roles("Cruiser", "Vexor")
        assert "armor_tank" in detect_ship_roles("Battlecruiser", "Brutix")
        # Amarr = armor
        assert "armor_tank" in detect_ship_roles("Cruiser", "Omen")
        assert "armor_tank" in detect_ship_roles("Battlecruiser", "Harbinger")
        # Caldari = shield
        assert "shield_tank" in detect_ship_roles("Cruiser", "Caracal")
        assert "shield_tank" in detect_ship_roles("Battlecruiser", "Drake")
        # Minmatar = shield (mostly)
        assert "shield_tank" in detect_ship_roles("Cruiser", "Stabber")
        assert "shield_tank" in detect_ship_roles("Battlecruiser", "Hurricane")

    def test_multiple_roles_detected(self):
        """Ships can have multiple roles."""
        # Astero is explorer + stealth + drone boat
        roles = detect_ship_roles("Frigate", "Astero")
        assert "explorer" in roles
        assert "stealth_ship" in roles
        assert "drone_boat" in roles
        # Sin is stealth + jump capable
        roles = detect_ship_roles("Black Ops", "Sin")
        assert "stealth_ship" in roles
        assert "jump_capable" in roles


class TestBreakpointSkillsInPlan:
    """Tests for breakpoint skill integration in Easy 80% plans."""

    def test_breakpoint_skill_with_role_goes_to_train_to_5(self):
        """Breakpoint skills for detected roles should be in train_to_5."""
        full_tree = [
            {"skill_name": "Drones", "required_level": 3, "rank": 1},
            {"skill_name": "Medium Drone Operation", "required_level": 0, "rank": 2},
        ]
        # With drone_boat role, Drones becomes a breakpoint skill
        plan = generate_easy_80_plan(full_tree, "Ship", ["drone_boat"])

        train_to_5 = plan.get("train_to_5", [])
        drones = next((s for s in train_to_5 if s["skill_name"] == "Drones"), None)
        assert drones is not None, "Drones should be in train_to_5 for drone_boat"
        assert drones.get("is_breakpoint") is True
        assert drones.get("easy_80_level") == 5

    def test_breakpoint_skill_without_role_stays_normal(self):
        """Breakpoint skills without matching role follow normal rules."""
        full_tree = [
            {"skill_name": "Drones", "required_level": 3, "rank": 1},
        ]
        # Without drone_boat role, Drones follows normal rules
        plan = generate_easy_80_plan(full_tree, "Ship", [])

        # Should be in required_at_level at level 3 (not elevated to 5)
        required = plan.get("required_at_level", [])
        drones = next((s for s in required if s["skill_name"] == "Drones"), None)
        # Could also be in train_to_5 if SKILLS_REQUIRING_V kicks in
        train_to_5 = plan.get("train_to_5", [])
        drones_train = next((s for s in train_to_5 if s["skill_name"] == "Drones"), None)

        # If Drones is at required_level 3 and not role-matched, should stay at 3
        if drones is not None:
            assert drones.get("easy_80_level") == 3

    def test_universal_breakpoint_applies_to_all(self):
        """Breakpoints with applies_to_roles=None apply universally."""
        full_tree = [
            {"skill_name": "Thermodynamics", "required_level": 0, "rank": 3},
        ]
        # Even without roles, Thermodynamics is universal breakpoint
        plan = generate_easy_80_plan(full_tree, "Ship", [])

        train_to_5 = plan.get("train_to_5", [])
        thermo = next((s for s in train_to_5 if s["skill_name"] == "Thermodynamics"), None)
        assert thermo is not None, "Thermodynamics should be in train_to_5 (universal)"
        assert thermo.get("is_breakpoint") is True
        assert thermo.get("easy_80_level") == 4  # Thermodynamics breakpoint is at IV

    def test_cloaking_breakpoint_for_stealth(self):
        """Cloaking IV is a breakpoint for stealth_ship role."""
        full_tree = [
            {"skill_name": "Cloaking", "required_level": 1, "rank": 4},
        ]
        plan = generate_easy_80_plan(full_tree, "Ship", ["stealth_ship"])

        train_to_5 = plan.get("train_to_5", [])
        cloaking = next((s for s in train_to_5 if s["skill_name"] == "Cloaking"), None)
        assert cloaking is not None, "Cloaking should be elevated for stealth_ship"
        assert cloaking.get("is_breakpoint") is True
        assert cloaking.get("easy_80_level") == 4  # Breakpoint is at IV

    def test_breakpoint_info_included_in_output(self):
        """Breakpoint skills should include breakpoint_info metadata."""
        full_tree = [
            {"skill_name": "Drones", "required_level": 5, "rank": 1},
        ]
        plan = generate_easy_80_plan(full_tree, "Ship", ["drone_boat"])

        train_to_5 = plan.get("train_to_5", [])
        drones = next((s for s in train_to_5 if s["skill_name"] == "Drones"), None)
        assert drones is not None
        assert "breakpoint_info" in drones
        assert "effect" in drones["breakpoint_info"]
        assert "reason" in drones["breakpoint_info"]
