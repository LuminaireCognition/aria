"""
Tests for aria_esi.mcp.market.clipboard

Tests EVE Online clipboard parsing for various formats.
"""



class TestParseClipboard:
    """Tests for parse_clipboard function."""

    def test_empty_input(self):
        from aria_esi.mcp.market.clipboard import parse_clipboard

        assert parse_clipboard("") == []
        assert parse_clipboard("   ") == []
        assert parse_clipboard("\n\n") == []

    def test_tab_separated_format(self):
        """Tab-separated is the most common clipboard format from inventory."""
        from aria_esi.mcp.market.clipboard import parse_clipboard

        text = "Tritanium\t1000\nPyerite\t500"
        result = parse_clipboard(text)

        assert len(result) == 2
        assert result[0].name == "Tritanium"
        assert result[0].quantity == 1000
        assert result[1].name == "Pyerite"
        assert result[1].quantity == 500

    def test_tab_separated_with_commas(self):
        """Quantities may include comma separators."""
        from aria_esi.mcp.market.clipboard import parse_clipboard

        text = "Tritanium\t1,000,000\nPyerite\t500,000"
        result = parse_clipboard(text)

        assert len(result) == 2
        assert result[0].quantity == 1000000
        assert result[1].quantity == 500000

    def test_inventory_window_format(self):
        """Inventory window shows 'Quantity: X' format."""
        from aria_esi.mcp.market.clipboard import parse_clipboard

        text = "Tritanium    Quantity: 1,000\nPyerite    Quantity: 500"
        result = parse_clipboard(text)

        assert len(result) == 2
        assert result[0].name == "Tritanium"
        assert result[0].quantity == 1000
        assert result[1].name == "Pyerite"
        assert result[1].quantity == 500

    def test_multi_buy_format(self):
        """Multi-buy format uses 'x100' notation."""
        from aria_esi.mcp.market.clipboard import parse_clipboard

        text = "Tritanium x1000\nPyerite x500"
        result = parse_clipboard(text)

        assert len(result) == 2
        assert result[0].name == "Tritanium"
        assert result[0].quantity == 1000
        assert result[1].name == "Pyerite"
        assert result[1].quantity == 500

    def test_multi_buy_format_uppercase_x(self):
        """Multi-buy format may use uppercase X."""
        from aria_esi.mcp.market.clipboard import parse_clipboard

        text = "PLEX X10"
        result = parse_clipboard(text)

        assert len(result) == 1
        assert result[0].name == "PLEX"
        assert result[0].quantity == 10

    def test_contract_format(self):
        """Contract format uses 'X unit(s)' notation."""
        from aria_esi.mcp.market.clipboard import parse_clipboard

        text = "Tritanium 1000 units\nPyerite 500 unit"
        result = parse_clipboard(text)

        assert len(result) == 2
        assert result[0].name == "Tritanium"
        assert result[0].quantity == 1000
        assert result[1].name == "Pyerite"
        assert result[1].quantity == 500

    def test_item_name_only(self):
        """Item name only defaults to quantity 1."""
        from aria_esi.mcp.market.clipboard import parse_clipboard

        text = "Tritanium\nPyerite"
        result = parse_clipboard(text)

        assert len(result) == 2
        assert result[0].quantity == 1
        assert result[1].quantity == 1

    def test_mixed_formats(self):
        """Handle mixed formats in same input."""
        from aria_esi.mcp.market.clipboard import parse_clipboard

        text = """Tritanium\t1000
Pyerite    Quantity: 500
Mexallon x100
Isogen"""
        result = parse_clipboard(text)

        assert len(result) == 4
        assert result[0].quantity == 1000  # tab format
        assert result[1].quantity == 500  # inventory format
        assert result[2].quantity == 100  # multi-buy format
        assert result[3].quantity == 1  # name only

    def test_extra_whitespace(self):
        """Handle extra whitespace in input."""
        from aria_esi.mcp.market.clipboard import parse_clipboard

        text = "  Tritanium  \t  1000  \n  Pyerite  \t  500  "
        result = parse_clipboard(text)

        assert len(result) == 2
        assert result[0].name == "Tritanium"
        assert result[1].name == "Pyerite"

    def test_complex_item_names(self):
        """Handle item names with spaces and special characters."""
        from aria_esi.mcp.market.clipboard import parse_clipboard

        text = "Hobgoblin I\t100\nHeavy Assault Missile Launcher II\t5"
        result = parse_clipboard(text)

        assert len(result) == 2
        assert result[0].name == "Hobgoblin I"
        assert result[1].name == "Heavy Assault Missile Launcher II"


class TestParseQuantity:
    """Tests for _parse_quantity helper."""

    def test_basic_integer(self):
        from aria_esi.mcp.market.clipboard import _parse_quantity

        assert _parse_quantity("100") == 100
        assert _parse_quantity("1") == 1
        assert _parse_quantity("999999") == 999999

    def test_with_commas(self):
        from aria_esi.mcp.market.clipboard import _parse_quantity

        assert _parse_quantity("1,000") == 1000
        assert _parse_quantity("1,000,000") == 1000000
        assert _parse_quantity("1,234,567,890") == 1234567890

    def test_with_k_suffix(self):
        """Handle 'k' suffix for thousands."""
        from aria_esi.mcp.market.clipboard import _parse_quantity

        assert _parse_quantity("1k") == 1000
        assert _parse_quantity("1K") == 1000
        assert _parse_quantity("10k") == 10000
        assert _parse_quantity("1.5k") == 1500

    def test_with_m_suffix(self):
        """Handle 'm' suffix for millions."""
        from aria_esi.mcp.market.clipboard import _parse_quantity

        assert _parse_quantity("1m") == 1000000
        assert _parse_quantity("1M") == 1000000
        assert _parse_quantity("2.5m") == 2500000

    def test_empty_or_invalid(self):
        from aria_esi.mcp.market.clipboard import _parse_quantity

        assert _parse_quantity("") == 0
        assert _parse_quantity(None) == 0
        assert _parse_quantity("abc") == 0
        assert _parse_quantity("not a number") == 0

    def test_with_spaces(self):
        from aria_esi.mcp.market.clipboard import _parse_quantity

        assert _parse_quantity(" 100 ") == 100
        assert _parse_quantity("1 000") == 1000


class TestParseClipboardToDict:
    """Tests for parse_clipboard_to_dict convenience function."""

    def test_returns_dict_format(self):
        from aria_esi.mcp.market.clipboard import parse_clipboard_to_dict

        text = "Tritanium\t1000\nPyerite\t500"
        result = parse_clipboard_to_dict(text)

        assert len(result) == 2
        assert result[0] == {"name": "Tritanium", "quantity": 1000}
        assert result[1] == {"name": "Pyerite", "quantity": 500}

    def test_empty_returns_empty_list(self):
        from aria_esi.mcp.market.clipboard import parse_clipboard_to_dict

        assert parse_clipboard_to_dict("") == []


class TestItemsToDict:
    """Tests for items_to_dict helper."""

    def test_converts_parsed_items(self):
        from aria_esi.mcp.market.clipboard import ParsedItem, items_to_dict

        items = [
            ParsedItem(name="Tritanium", quantity=1000),
            ParsedItem(name="Pyerite", quantity=500),
        ]
        result = items_to_dict(items)

        assert result == [
            {"name": "Tritanium", "quantity": 1000},
            {"name": "Pyerite", "quantity": 500},
        ]

    def test_empty_list(self):
        from aria_esi.mcp.market.clipboard import items_to_dict

        assert items_to_dict([]) == []
