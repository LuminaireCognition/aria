"""
Tests for Industry Chain Resolution Service.
"""

import pytest

from aria_esi.services.industry_chains import (
    ChainNode,
    ChainResolver,
    ChainResolutionResult,
    format_chain_summary,
    get_always_terminal_materials,
    get_max_chain_depth,
)


class TestTerminalMaterials:
    """Test terminal materials configuration."""

    @pytest.mark.unit
    def test_minerals_are_terminal(self):
        """Standard minerals should be terminal."""
        terminals = get_always_terminal_materials()
        assert "Tritanium" in terminals
        assert "Pyerite" in terminals
        assert "Megacyte" in terminals
        assert "Morphite" in terminals

    @pytest.mark.unit
    def test_pi_p1_are_terminal(self):
        """PI P1 materials should be terminal."""
        terminals = get_always_terminal_materials()
        assert "Bacteria" in terminals
        assert "Water" in terminals
        assert "Oxygen" in terminals

    @pytest.mark.unit
    def test_max_depth_is_reasonable(self):
        """Max depth should be a sensible value."""
        max_depth = get_max_chain_depth()
        assert max_depth >= 3
        assert max_depth <= 10


class TestChainNode:
    """Test ChainNode data class."""

    @pytest.mark.unit
    def test_terminal_node_market_cost(self):
        """Terminal node should use market price."""
        node = ChainNode(
            type_name="Tritanium",
            type_id=34,
            quantity=1000,
            is_terminal=True,
            market_price=5.0,
        )
        assert node.total_market_cost == 5000.0
        assert node.total_build_cost == 5000.0  # Terminal = must buy
        assert node.savings == 0

    @pytest.mark.unit
    def test_buildable_node_with_children(self):
        """Buildable node should sum children's costs."""
        child1 = ChainNode(
            type_name="Tritanium",
            type_id=34,
            quantity=100,
            is_terminal=True,
            market_price=5.0,
        )
        child2 = ChainNode(
            type_name="Pyerite",
            type_id=35,
            quantity=50,
            is_terminal=True,
            market_price=10.0,
        )
        parent = ChainNode(
            type_name="Component",
            type_id=100,
            quantity=1,
            is_terminal=False,
            market_price=2000.0,
            children=[child1, child2],
        )
        # Market cost = parent price * quantity
        assert parent.total_market_cost == 2000.0
        # Build cost = sum of children
        assert parent.total_build_cost == 500.0 + 500.0  # 100*5 + 50*10
        # Savings
        assert parent.savings == 2000.0 - 1000.0  # 1000 ISK saved

    @pytest.mark.unit
    def test_node_to_dict(self):
        """Node should serialize to dict."""
        node = ChainNode(
            type_name="Tritanium",
            type_id=34,
            quantity=100,
            is_terminal=True,
            terminal_reason="raw_material",
            market_price=5.0,
        )
        d = node.to_dict()
        assert d["type_name"] == "Tritanium"
        assert d["type_id"] == 34
        assert d["quantity"] == 100
        assert d["is_terminal"] is True
        assert d["terminal_reason"] == "raw_material"
        assert d["total_market_cost"] == 500.0


class TestChainResolver:
    """Test chain resolution logic."""

    @pytest.fixture
    def mock_sde_lookup(self):
        """Mock SDE lookup function."""
        blueprints = {
            "Test Component": {
                "product": "Test Component",
                "product_type_id": 100,
                "blueprint_type_id": 1100,
                "materials": [
                    {"type_name": "Tritanium", "type_id": 34, "quantity": 100},
                    {"type_name": "Pyerite", "type_id": 35, "quantity": 50},
                ],
            },
            "Complex Item": {
                "product": "Complex Item",
                "product_type_id": 200,
                "blueprint_type_id": 1200,
                "materials": [
                    {"type_name": "Test Component", "type_id": 100, "quantity": 2},
                    {"type_name": "Mexallon", "type_id": 36, "quantity": 25},
                ],
            },
        }

        def lookup(item_name):
            if item_name in blueprints:
                return blueprints[item_name]
            return {"error": f"No blueprint found for {item_name}"}

        return lookup

    @pytest.fixture
    def mock_market_lookup(self):
        """Mock market lookup function."""
        prices = {
            "Tritanium": 5.0,
            "Pyerite": 10.0,
            "Mexallon": 50.0,
            "Test Component": 2000.0,
            "Complex Item": 10000.0,
        }

        def lookup(item_names):
            items = []
            for name in item_names:
                if name in prices:
                    items.append({
                        "type_name": name,
                        "sell_min": prices[name],
                    })
            return {"items": items}

        return lookup

    @pytest.mark.unit
    def test_resolve_simple_item(self, mock_sde_lookup, mock_market_lookup):
        """Resolve a simple item with only mineral inputs."""
        resolver = ChainResolver(
            sde_lookup=mock_sde_lookup,
            market_lookup=mock_market_lookup,
            me_level=0,
            runs=1,
        )
        result = resolver.resolve("Test Component")

        assert result.root.type_name == "Test Component"
        assert len(result.root.children) == 2
        assert result.max_depth_reached == 1

        # Check terminal materials collected
        terminal_names = [m["type_name"] for m in result.terminal_materials]
        assert "Tritanium" in terminal_names
        assert "Pyerite" in terminal_names

    @pytest.mark.unit
    def test_resolve_nested_chain(self, mock_sde_lookup, mock_market_lookup):
        """Resolve item with nested component."""
        resolver = ChainResolver(
            sde_lookup=mock_sde_lookup,
            market_lookup=mock_market_lookup,
            me_level=0,
            runs=1,
        )
        result = resolver.resolve("Complex Item")

        # Should go 2 levels deep
        assert result.max_depth_reached == 2

        # Check that Test Component is in buildable components
        buildable_names = [c["type_name"] for c in result.buildable_components]
        assert "Test Component" in buildable_names

    @pytest.mark.unit
    def test_me_reduction_applied(self, mock_sde_lookup, mock_market_lookup):
        """ME level should reduce material quantities."""
        resolver_me0 = ChainResolver(
            sde_lookup=mock_sde_lookup,
            market_lookup=mock_market_lookup,
            me_level=0,
            runs=1,
        )
        resolver_me10 = ChainResolver(
            sde_lookup=mock_sde_lookup,
            market_lookup=mock_market_lookup,
            me_level=10,
            runs=1,
        )

        result_me0 = resolver_me0.resolve("Test Component")
        result_me10 = resolver_me10.resolve("Test Component")

        # ME 10 should have lower quantities
        me0_trit = next(
            m for m in result_me0.terminal_materials
            if m["type_name"] == "Tritanium"
        )
        me10_trit = next(
            m for m in result_me10.terminal_materials
            if m["type_name"] == "Tritanium"
        )
        assert me10_trit["quantity"] < me0_trit["quantity"]

    @pytest.mark.unit
    def test_no_blueprint_returns_terminal(self, mock_sde_lookup, mock_market_lookup):
        """Item without blueprint should be marked terminal."""
        resolver = ChainResolver(
            sde_lookup=mock_sde_lookup,
            market_lookup=mock_market_lookup,
            me_level=0,
            runs=1,
        )
        result = resolver.resolve("Unknown Item")

        assert result.root.is_terminal is True
        assert result.root.terminal_reason is not None
        assert len(result.warnings) > 0

    @pytest.mark.unit
    def test_depth_limit_enforced(self, mock_market_lookup):
        """Chain should stop at max depth."""
        # Create a deeply nested mock
        def deep_lookup(item_name):
            # Everything refers to itself with different name
            return {
                "product": item_name,
                "product_type_id": hash(item_name) % 10000,
                "blueprint_type_id": hash(item_name) % 10000 + 10000,
                "materials": [
                    {
                        "type_name": f"{item_name}_child",
                        "type_id": hash(f"{item_name}_child") % 10000,
                        "quantity": 1,
                    }
                ],
            }

        resolver = ChainResolver(
            sde_lookup=deep_lookup,
            market_lookup=mock_market_lookup,
            me_level=0,
            runs=1,
        )
        result = resolver.resolve("Level0")

        # Should stop at max depth
        max_depth = get_max_chain_depth()
        assert result.max_depth_reached <= max_depth + 1


class TestChainResolutionResult:
    """Test result formatting."""

    @pytest.mark.unit
    def test_result_to_dict(self):
        """Result should serialize to dict."""
        root = ChainNode(
            type_name="Test",
            type_id=1,
            quantity=1,
            is_terminal=False,
            market_price=1000.0,
            children=[
                ChainNode(
                    type_name="Material",
                    type_id=2,
                    quantity=10,
                    is_terminal=True,
                    market_price=50.0,
                )
            ],
        )
        result = ChainResolutionResult(
            root=root,
            total_market_cost=1000.0,
            total_build_cost=500.0,
            savings=500.0,
            max_depth_reached=1,
            terminal_materials=[{"type_name": "Material", "quantity": 10}],
            buildable_components=[],
        )

        d = result.to_dict()
        assert d["total_market_cost"] == 1000.0
        assert d["total_build_cost"] == 500.0
        assert d["savings"] == 500.0
        assert d["savings_percent"] == 50.0


class TestFormatChainSummary:
    """Test markdown formatting."""

    @pytest.mark.unit
    def test_format_with_savings(self):
        """Format should show savings when profitable."""
        root = ChainNode(
            type_name="Ship",
            type_id=1,
            quantity=1,
            is_terminal=False,
            market_price=100_000_000.0,
            children=[
                ChainNode(
                    type_name="Tritanium",
                    type_id=34,
                    quantity=1_000_000,
                    is_terminal=True,
                    terminal_reason="raw_material",
                    market_price=5.0,
                )
            ],
        )
        result = ChainResolutionResult(
            root=root,
            total_market_cost=100_000_000.0,
            total_build_cost=5_000_000.0,
            savings=95_000_000.0,
            max_depth_reached=1,
            terminal_materials=[
                {"type_name": "Tritanium", "quantity": 1_000_000, "reason": "raw_material"}
            ],
            buildable_components=[],
        )

        output = format_chain_summary(result)

        assert "Build vs Buy Analysis: Ship" in output
        assert "Savings" in output
        assert "Tritanium" in output
        assert "Mining/PI/Moon" in output

    @pytest.mark.unit
    def test_format_with_loss(self):
        """Format should show loss when building is more expensive."""
        root = ChainNode(
            type_name="Item",
            type_id=1,
            quantity=1,
            is_terminal=False,
            market_price=1_000_000.0,
            children=[
                ChainNode(
                    type_name="Expensive Material",
                    type_id=2,
                    quantity=100,
                    is_terminal=True,
                    terminal_reason="no_blueprint",
                    market_price=20_000.0,
                )
            ],
        )
        result = ChainResolutionResult(
            root=root,
            total_market_cost=1_000_000.0,
            total_build_cost=2_000_000.0,
            savings=-1_000_000.0,
            max_depth_reached=1,
            terminal_materials=[
                {"type_name": "Expensive Material", "quantity": 100, "reason": "no_blueprint"}
            ],
            buildable_components=[],
        )

        output = format_chain_summary(result)

        assert "Loss if Building" in output
