"""
Tests for archetypes pricing module.

Tests EFT parsing for pricing, price estimation, and archetype price updates.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from aria_esi.archetypes.pricing import (
    FitPriceEstimate,
    ItemPrice,
    _fetch_prices_from_market,
    _parse_eft_for_pricing,
    estimate_fit_price,
    update_archetype_price,
)

# =============================================================================
# ItemPrice Tests
# =============================================================================


class TestItemPrice:
    """Tests for ItemPrice dataclass."""

    def test_create_item_price(self) -> None:
        """Test creating ItemPrice with all fields."""
        item = ItemPrice(
            type_name="Drone Damage Amplifier II",
            quantity=2,
            unit_price=1_500_000.0,
            total_price=3_000_000.0,
            price_source="jita",
        )

        assert item.type_name == "Drone Damage Amplifier II"
        assert item.quantity == 2
        assert item.unit_price == 1_500_000.0
        assert item.total_price == 3_000_000.0
        assert item.price_source == "jita"

    def test_item_price_default_source(self) -> None:
        """Test ItemPrice default price_source."""
        item = ItemPrice(
            type_name="Test",
            quantity=1,
            unit_price=100.0,
            total_price=100.0,
        )

        assert item.price_source == "jita"


# =============================================================================
# FitPriceEstimate Tests
# =============================================================================


class TestFitPriceEstimate:
    """Tests for FitPriceEstimate dataclass."""

    def test_to_dict_basic(self) -> None:
        """Test FitPriceEstimate.to_dict() with basic data."""
        estimate = FitPriceEstimate(
            total_isk=50_000_000,
            ship_price=15_000_000.0,
            modules_price=25_000_000.0,
            rigs_price=5_000_000.0,
            drones_price=5_000_000.0,
            charges_price=0.0,
            price_source="jita",
            updated="2026-01-15",
        )

        result = estimate.to_dict()
        assert result["total_isk"] == 50_000_000
        assert result["ship_price"] == 15_000_000.0
        assert result["modules_price"] == 25_000_000.0
        assert result["rigs_price"] == 5_000_000.0
        assert result["drones_price"] == 5_000_000.0
        assert result["charges_price"] == 0.0
        assert result["price_source"] == "jita"
        assert result["updated"] == "2026-01-15"
        assert result["breakdown_count"] == 0
        assert result["warnings"] == []

    def test_to_dict_with_breakdown(self) -> None:
        """Test FitPriceEstimate.to_dict() with breakdown items."""
        estimate = FitPriceEstimate(
            total_isk=50_000_000,
            breakdown=[
                ItemPrice("Module A", 2, 1_000_000.0, 2_000_000.0),
                ItemPrice("Module B", 1, 3_000_000.0, 3_000_000.0),
            ],
        )

        result = estimate.to_dict()
        assert result["breakdown_count"] == 2

    def test_to_dict_with_warnings(self) -> None:
        """Test FitPriceEstimate.to_dict() with warnings."""
        estimate = FitPriceEstimate(
            total_isk=0,
            warnings=["No price found for ship: Unknown Ship"],
        )

        result = estimate.to_dict()
        assert len(result["warnings"]) == 1


# =============================================================================
# EFT Parsing Tests
# =============================================================================


class TestParseEftForPricing:
    """Tests for _parse_eft_for_pricing function."""

    def test_parse_basic_eft(self, sample_eft_string: str) -> None:
        """Test parsing basic EFT format."""
        result = _parse_eft_for_pricing(sample_eft_string)

        assert result["ship"] == "Vexor"
        assert len(result["modules"]) > 0
        assert len(result["drones"]) > 0

    def test_parse_ship_name(self) -> None:
        """Test parsing ship name from header."""
        eft = "[Drake, My Drake Fit]\nMissile Guidance Enhancer II"

        result = _parse_eft_for_pricing(eft)

        assert result["ship"] == "Drake"

    def test_parse_empty_eft(self) -> None:
        """Test parsing empty EFT string."""
        result = _parse_eft_for_pricing("")

        assert result["ship"] is None
        assert result["modules"] == []
        assert result["rigs"] == []
        assert result["drones"] == []
        assert result["charges"] == []

    def test_parse_module_quantities(self) -> None:
        """Test modules are counted correctly."""
        eft = """[Vexor, Test]
Drone Damage Amplifier II
Drone Damage Amplifier II
Drone Damage Amplifier II
"""
        result = _parse_eft_for_pricing(eft)

        # Find DDA in modules
        dda = [m for m in result["modules"] if "Drone Damage Amplifier" in m[0]]
        assert len(dda) == 1
        assert dda[0][1] == 3  # quantity

    def test_parse_drones_with_quantity(self) -> None:
        """Test parsing drones with x quantity syntax."""
        eft = """[Vexor, Test]
Hobgoblin II x5
Hammerhead II x3
"""
        result = _parse_eft_for_pricing(eft)

        assert len(result["drones"]) == 2
        # Check quantities
        drone_dict = dict(result["drones"])
        assert drone_dict["Hobgoblin II"] == 5
        assert drone_dict["Hammerhead II"] == 3

    def test_parse_modules_with_charges(self, sample_eft_with_charges: str) -> None:
        """Test parsing modules with loaded charges."""
        result = _parse_eft_for_pricing(sample_eft_with_charges)

        # Should have charges extracted
        assert len(result["charges"]) > 0
        charge_names = [c[0] for c in result["charges"]]
        assert "Nanite Repair Paste" in charge_names

    def test_parse_rigs_identified(self) -> None:
        """Test rigs are identified correctly."""
        # Use known rig patterns from the pricing module:
        # "pump", "purifier", "trimark", "rig", "field extender"
        eft = """[Vexor, Test]
Medium Auxiliary Nano Pump I
Medium Trimark Armor Pump I
Medium Anti-EM Screen Reinforcer I
"""
        result = _parse_eft_for_pricing(eft)

        # Pump rigs should be identified as rigs
        pump_rigs = [r for r in result["rigs"] if "Pump" in r[0]]
        assert len(pump_rigs) == 2
        # The "Reinforcer" doesn't match any rig pattern, so it goes to modules
        # This is a limitation of the pattern-based detection

    def test_parse_skips_empty_slots(self) -> None:
        """Test empty slot markers are skipped."""
        eft = """[Vexor, Test]
[Empty Low slot]
[Empty Mid slot]
[Empty High slot]
Drone Damage Amplifier II
"""
        result = _parse_eft_for_pricing(eft)

        # Should only have the DDA
        assert len(result["modules"]) == 1

    def test_parse_handles_offline_modules(self) -> None:
        """Test offline module markers are handled."""
        eft = """[Vexor, Test]
Drone Damage Amplifier II/OFFLINE
"""
        result = _parse_eft_for_pricing(eft)

        # Should strip /OFFLINE marker
        assert len(result["modules"]) == 1
        assert result["modules"][0][0] == "Drone Damage Amplifier II"


# =============================================================================
# Price Fetching Tests
# =============================================================================


class TestFetchPricesFromMarket:
    """Tests for _fetch_prices_from_market function."""

    def test_fetch_prices_success(self) -> None:
        """Test fetching prices from market database."""
        with patch(
            "aria_esi.mcp.market.database.get_market_database"
        ) as mock_get_db, patch(
            "aria_esi.models.market.resolve_trade_hub"
        ) as mock_resolve:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_type_info = MagicMock()
            mock_type_info.type_id = 2456
            mock_db.resolve_type_name.return_value = mock_type_info

            mock_aggregate = MagicMock()
            mock_aggregate.sell_min = 1_500_000.0
            mock_aggregate.sell_weighted_avg = 1_600_000.0
            mock_db.get_aggregate.return_value = mock_aggregate

            mock_resolve.return_value = {"region_id": 10000002}

            prices = _fetch_prices_from_market(
                ["Drone Damage Amplifier II"], region="jita"
            )

            assert "Drone Damage Amplifier II" in prices
            assert prices["Drone Damage Amplifier II"] == 1_500_000.0

    def test_fetch_prices_fallback_to_weighted(self) -> None:
        """Test fallback to weighted average when min is 0."""
        with patch(
            "aria_esi.mcp.market.database.get_market_database"
        ) as mock_get_db, patch(
            "aria_esi.models.market.resolve_trade_hub"
        ) as mock_resolve:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_type_info = MagicMock()
            mock_type_info.type_id = 2456
            mock_db.resolve_type_name.return_value = mock_type_info

            mock_aggregate = MagicMock()
            mock_aggregate.sell_min = 0  # No min price
            mock_aggregate.sell_weighted_avg = 1_600_000.0
            mock_db.get_aggregate.return_value = mock_aggregate

            mock_resolve.return_value = {"region_id": 10000002}

            prices = _fetch_prices_from_market(["Test Item"], region="jita")

            assert prices["Test Item"] == 1_600_000.0

    def test_fetch_prices_no_data(self) -> None:
        """Test when no price data is available."""
        with patch(
            "aria_esi.mcp.market.database.get_market_database"
        ) as mock_get_db, patch(
            "aria_esi.models.market.resolve_trade_hub"
        ) as mock_resolve:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.resolve_type_name.return_value = None  # Item not found

            mock_resolve.return_value = {"region_id": 10000002}

            prices = _fetch_prices_from_market(["Unknown Item"])

            assert "Unknown Item" not in prices

    def test_fetch_prices_database_unavailable(self) -> None:
        """Test graceful handling when database is unavailable."""
        with patch(
            "aria_esi.mcp.market.database.get_market_database"
        ) as mock_get_db:
            mock_get_db.side_effect = ImportError("Database not available")

            prices = _fetch_prices_from_market(["Test Item"])

            assert prices == {}


# =============================================================================
# Estimate Fit Price Tests
# =============================================================================


class TestEstimateFitPrice:
    """Tests for estimate_fit_price function."""

    def test_estimate_fit_price_basic(
        self, sample_eft_string: str, mock_market_prices: dict[str, float]
    ) -> None:
        """Test basic fit price estimation."""
        with patch(
            "aria_esi.archetypes.pricing._fetch_prices_from_market"
        ) as mock_fetch:
            mock_fetch.return_value = mock_market_prices

            result = estimate_fit_price(sample_eft_string)

            assert result.total_isk > 0
            assert result.ship_price > 0
            assert result.price_source == "jita"
            assert result.updated != ""

    def test_estimate_fit_price_with_region(self, sample_eft_string: str) -> None:
        """Test fit price estimation with specific region."""
        with patch(
            "aria_esi.archetypes.pricing._fetch_prices_from_market"
        ) as mock_fetch:
            mock_fetch.return_value = {"Vexor": 15_000_000.0}

            result = estimate_fit_price(sample_eft_string, region="amarr")

            assert result.price_source == "amarr"
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args
            assert call_args[0][1] == "amarr"  # Second positional arg

    def test_estimate_fit_price_invalid_eft(self) -> None:
        """Test price estimation with invalid EFT."""
        result = estimate_fit_price("invalid eft without ship header")

        assert result.total_isk == 0
        assert len(result.warnings) > 0
        assert "Could not parse ship" in result.warnings[0]

    def test_estimate_fit_price_missing_prices(self) -> None:
        """Test price estimation with some missing prices."""
        eft = """[UnknownShip, Test]
Unknown Module A
Unknown Module B
"""
        with patch(
            "aria_esi.archetypes.pricing._fetch_prices_from_market"
        ) as mock_fetch:
            mock_fetch.return_value = {}  # No prices available

            result = estimate_fit_price(eft)

            assert result.total_isk == 0
            assert len(result.warnings) > 0

    def test_estimate_fit_price_breakdown(
        self, sample_eft_string: str, mock_market_prices: dict[str, float]
    ) -> None:
        """Test price breakdown is populated."""
        with patch(
            "aria_esi.archetypes.pricing._fetch_prices_from_market"
        ) as mock_fetch:
            mock_fetch.return_value = mock_market_prices

            result = estimate_fit_price(sample_eft_string)

            assert len(result.breakdown) > 0
            # Verify breakdown items have correct structure
            for item in result.breakdown:
                assert hasattr(item, "type_name")
                assert hasattr(item, "quantity")
                assert hasattr(item, "unit_price")
                assert hasattr(item, "total_price")

    def test_estimate_fit_price_charges_not_in_total(
        self, sample_eft_with_charges: str, mock_market_prices: dict[str, float]
    ) -> None:
        """Test charges are tracked but not included in total."""
        with patch(
            "aria_esi.archetypes.pricing._fetch_prices_from_market"
        ) as mock_fetch:
            mock_fetch.return_value = {
                **mock_market_prices,
                "Nanite Repair Paste": 50_000.0,
            }

            result = estimate_fit_price(sample_eft_with_charges)

            # Charges price should be tracked separately
            assert result.charges_price >= 0
            # But total should not include charges
            total_without_charges = (
                result.ship_price
                + result.modules_price
                + result.rigs_price
                + result.drones_price
            )
            assert result.total_isk == int(total_without_charges)


# =============================================================================
# Update Archetype Price Tests
# =============================================================================


class TestUpdateArchetypePrice:
    """Tests for update_archetype_price function."""

    def test_update_price_success(self) -> None:
        """Test successful price update."""
        mock_archetype = MagicMock()
        mock_archetype.eft = "[Vexor, Test]\nDrone Damage Amplifier II"

        with patch(
            "aria_esi.archetypes.loader.ArchetypeLoader"
        ) as MockLoader, patch(
            "aria_esi.archetypes.pricing.estimate_fit_price"
        ) as mock_estimate:
            mock_loader = MockLoader.return_value
            mock_loader.get_archetype.return_value = mock_archetype

            mock_estimate.return_value = FitPriceEstimate(
                total_isk=50_000_000,
                updated="2026-01-15",
            )

            result = update_archetype_price("vexor/pve/missions/l2/meta")

            assert result["status"] == "calculated"
            assert result["estimated_isk"] == 50_000_000
            assert result["isk_updated"] == "2026-01-15"
            assert result["archetype_path"] == "vexor/pve/missions/l2/meta"

    def test_update_price_archetype_not_found(self) -> None:
        """Test price update when archetype not found."""
        with patch(
            "aria_esi.archetypes.loader.ArchetypeLoader"
        ) as MockLoader:
            mock_loader = MockLoader.return_value
            mock_loader.get_archetype.return_value = None

            result = update_archetype_price("unknown/path/t1")

            assert result["error"] == "not_found"
            assert "not found" in result["message"]

    def test_update_price_unavailable(self) -> None:
        """Test price update when prices unavailable."""
        mock_archetype = MagicMock()
        mock_archetype.eft = "[Vexor, Test]\nUnknown Module"

        with patch(
            "aria_esi.archetypes.loader.ArchetypeLoader"
        ) as MockLoader, patch(
            "aria_esi.archetypes.pricing.estimate_fit_price"
        ) as mock_estimate:
            mock_loader = MockLoader.return_value
            mock_loader.get_archetype.return_value = mock_archetype

            mock_estimate.return_value = FitPriceEstimate(
                total_isk=0,
                warnings=["No prices available"],
            )

            result = update_archetype_price("vexor/pve/missions/l2/meta")

            assert result["error"] == "price_unavailable"
            assert len(result["warnings"]) > 0

    def test_update_price_with_region(self) -> None:
        """Test price update with specific region."""
        mock_archetype = MagicMock()
        mock_archetype.eft = "[Vexor, Test]"

        with patch(
            "aria_esi.archetypes.loader.ArchetypeLoader"
        ) as MockLoader, patch(
            "aria_esi.archetypes.pricing.estimate_fit_price"
        ) as mock_estimate:
            mock_loader = MockLoader.return_value
            mock_loader.get_archetype.return_value = mock_archetype

            mock_estimate.return_value = FitPriceEstimate(
                total_isk=50_000_000,
                price_source="amarr",
            )

            update_archetype_price("vexor/pve/missions/l2/meta", region="amarr")

            mock_estimate.assert_called_once()
            call_args = mock_estimate.call_args
            assert call_args[0][1] == "amarr"  # Second positional arg
