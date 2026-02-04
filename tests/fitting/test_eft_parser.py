"""
Tests for EFT (EVE Fitting Tool) Format Parser.

Tests cover:
- Header parsing (valid, special chars, malformed)
- Module parsing (simple, with charge, offline)
- Quantity parsing (drones, cargo)
- Section transitions
- Type resolution errors
- Empty slot markers
"""

from __future__ import annotations

import pytest

from aria_esi.fitting.eft_parser import (
    HEADER_PATTERN,
    MODULE_PATTERN,
    QUANTITY_PATTERN,
    EFTParseError,
    EFTParser,
    ParseSection,
    TypeResolutionError,
)

# =============================================================================
# Header Pattern Tests
# =============================================================================


class TestHeaderPattern:
    """Tests for EFT header regex pattern."""

    def test_valid_header_standard(self):
        """Test standard header format."""
        match = HEADER_PATTERN.match("[Vexor, My PvE Fit]")
        assert match is not None
        assert match.group("ship_type") == "Vexor"
        assert match.group("fit_name") == "My PvE Fit"

    def test_valid_header_with_spaces(self):
        """Test header with extra spaces."""
        match = HEADER_PATTERN.match("[Vexor,  My PvE Fit ]")
        assert match is not None
        assert match.group("ship_type") == "Vexor"
        # Regex pattern uses \s* after comma, so leading space is consumed
        assert match.group("fit_name") == "My PvE Fit "

    def test_valid_header_special_chars(self):
        """Test header with special characters in fit name."""
        match = HEADER_PATTERN.match("[Vexor Navy Issue, L4 Mission (v2.1)]")
        assert match is not None
        assert match.group("ship_type") == "Vexor Navy Issue"
        assert match.group("fit_name") == "L4 Mission (v2.1)"

    def test_valid_header_unicode(self):
        """Test header with unicode characters."""
        match = HEADER_PATTERN.match("[Rifter, Minmatar Pride \u2605]")
        assert match is not None
        assert match.group("fit_name") == "Minmatar Pride \u2605"

    def test_invalid_header_missing_comma(self):
        """Test header without comma separator."""
        match = HEADER_PATTERN.match("[Vexor My Fit]")
        assert match is None

    def test_invalid_header_no_brackets(self):
        """Test header without brackets."""
        match = HEADER_PATTERN.match("Vexor, My Fit")
        assert match is None

    def test_invalid_header_empty_ship(self):
        """Test header with empty ship type."""
        match = HEADER_PATTERN.match("[, My Fit]")
        assert match is None

    def test_invalid_header_empty_name(self):
        """Test header with empty fit name (still matches)."""
        match = HEADER_PATTERN.match("[Vexor, ]")
        assert match is not None
        assert match.group("fit_name").strip() == ""


# =============================================================================
# Module Pattern Tests
# =============================================================================


class TestModulePattern:
    """Tests for module line regex pattern."""

    def test_simple_module(self):
        """Test simple module without charge or offline."""
        match = MODULE_PATTERN.match("Drone Damage Amplifier II")
        assert match is not None
        assert match.group("type_name") == "Drone Damage Amplifier II"
        assert match.group("charge_name") is None
        assert match.group("offline") is None

    def test_module_with_charge(self):
        """Test module with charge loaded."""
        match = MODULE_PATTERN.match("Rapid Light Missile Launcher II, Scourge Fury Light Missile")
        assert match is not None
        assert match.group("type_name") == "Rapid Light Missile Launcher II"
        assert match.group("charge_name") == "Scourge Fury Light Missile"
        assert match.group("offline") is None

    def test_module_offline(self):
        """Test offline module."""
        match = MODULE_PATTERN.match("Drone Damage Amplifier II /OFFLINE")
        assert match is not None
        assert match.group("type_name") == "Drone Damage Amplifier II"
        assert match.group("offline") == "OFFLINE"

    def test_module_offline_lowercase(self):
        """Test offline module with lowercase marker."""
        match = MODULE_PATTERN.match("Drone Damage Amplifier II /offline")
        assert match is not None
        assert match.group("offline") == "offline"

    def test_module_with_charge_and_offline(self):
        """Test module with both charge and offline."""
        match = MODULE_PATTERN.match("Heavy Missile Launcher II, Scourge Heavy Missile /OFFLINE")
        assert match is not None
        assert match.group("type_name") == "Heavy Missile Launcher II"
        assert match.group("charge_name") == "Scourge Heavy Missile"
        assert match.group("offline") == "OFFLINE"


# =============================================================================
# Quantity Pattern Tests
# =============================================================================


class TestQuantityPattern:
    """Tests for drone/cargo quantity pattern."""

    def test_drone_quantity(self):
        """Test standard drone quantity format."""
        match = QUANTITY_PATTERN.match("Hammerhead II x5")
        assert match is not None
        assert match.group("type_name") == "Hammerhead II"
        assert match.group("quantity") == "5"

    def test_cargo_quantity(self):
        """Test cargo quantity format."""
        match = QUANTITY_PATTERN.match("Nanite Repair Paste x100")
        assert match is not None
        assert match.group("type_name") == "Nanite Repair Paste"
        assert match.group("quantity") == "100"

    def test_quantity_large_number(self):
        """Test large quantity."""
        match = QUANTITY_PATTERN.match("Cap Booster 800 x5000")
        assert match is not None
        assert match.group("quantity") == "5000"

    def test_no_quantity_treated_as_module(self):
        """Test that line without x<n> doesn't match quantity pattern."""
        match = QUANTITY_PATTERN.match("Drone Damage Amplifier II")
        assert match is None


# =============================================================================
# Parser Tests
# =============================================================================


class TestEFTParser:
    """Tests for the full EFT parser."""

    def test_parse_basic_fit(self, mock_market_db):
        """Test parsing a basic fit."""
        eft = """[Vexor, Test Fit]
Drone Damage Amplifier II
"""
        parser = EFTParser(mock_market_db)
        fit = parser.parse(eft)

        assert fit.ship_type_id == 626
        assert fit.ship_type_name == "Vexor"
        assert fit.fit_name == "Test Fit"
        assert len(fit.low_slots) == 1
        assert fit.low_slots[0].type_name == "Drone Damage Amplifier II"

    def test_parse_with_all_sections(self, mock_market_db, eft_vexor_string):
        """Test parsing fit with all section types."""
        parser = EFTParser(mock_market_db)
        fit = parser.parse(eft_vexor_string)

        assert fit.ship_type_id == 626
        assert len(fit.low_slots) == 3
        assert len(fit.mid_slots) == 1
        assert len(fit.high_slots) == 1
        assert len(fit.rigs) == 3
        assert len(fit.drones) == 2
        assert fit.drones[0].quantity == 5
        assert fit.drones[1].quantity == 5

    def test_parse_offline_module(self, mock_market_db, eft_with_offline_module):
        """Test parsing fit with offline module."""
        parser = EFTParser(mock_market_db)
        fit = parser.parse(eft_with_offline_module)

        assert len(fit.low_slots) == 1
        assert fit.low_slots[0].is_offline is True

    def test_parse_module_with_charge(self, mock_market_db, eft_with_charge):
        """Test parsing fit with charged module."""
        parser = EFTParser(mock_market_db)
        fit = parser.parse(eft_with_charge)

        assert len(fit.high_slots) == 1
        module = fit.high_slots[0]
        assert module.type_id == 19739
        assert module.charge_type_id == 27361
        assert module.charge_name == "Scourge Fury Light Missile"

    def test_parse_empty_slots_skipped(self, mock_market_db, eft_with_empty_slots):
        """Test that empty slot markers are skipped."""
        parser = EFTParser(mock_market_db)
        fit = parser.parse(eft_with_empty_slots)

        # Only real modules should be parsed
        assert len(fit.low_slots) == 1
        assert fit.low_slots[0].type_name == "Drone Damage Amplifier II"

    def test_parse_empty_string_raises(self, mock_market_db):
        """Test parsing empty string raises error."""
        parser = EFTParser(mock_market_db)
        with pytest.raises(EFTParseError, match="Invalid header format"):
            parser.parse("")

    def test_parse_no_header_raises(self, mock_market_db, eft_invalid_no_header):
        """Test parsing without header raises error."""
        parser = EFTParser(mock_market_db)
        with pytest.raises(EFTParseError, match="Invalid header format"):
            parser.parse(eft_invalid_no_header)

    def test_parse_malformed_header_raises(self, mock_market_db, eft_malformed_header):
        """Test parsing malformed header raises error."""
        parser = EFTParser(mock_market_db)
        with pytest.raises(EFTParseError, match="Invalid header format"):
            parser.parse(eft_malformed_header)

    def test_parse_unknown_ship_raises(self, mock_market_db):
        """Test parsing unknown ship type raises TypeResolutionError."""
        eft = """[UnknownShipXYZ, Test]
Drone Damage Amplifier II
"""
        parser = EFTParser(mock_market_db)
        with pytest.raises(TypeResolutionError) as exc_info:
            parser.parse(eft)

        assert exc_info.value.type_name == "UnknownShipXYZ"

    def test_parse_unknown_module_raises(self, mock_market_db):
        """Test parsing unknown module raises TypeResolutionError."""
        eft = """[Vexor, Test]
Super Unknown Module X9000
"""
        parser = EFTParser(mock_market_db)
        with pytest.raises(TypeResolutionError) as exc_info:
            parser.parse(eft)

        assert exc_info.value.type_name == "Super Unknown Module X9000"


# =============================================================================
# Section Transition Tests
# =============================================================================


class TestSectionTransitions:
    """Tests for section detection and transitions."""

    def test_section_order(self, mock_market_db):
        """Test that sections transition in correct order."""
        # EFT format: low -> mid -> high -> rig -> subsystems -> drones -> cargo
        eft = """[Vexor, Section Test]
Drone Damage Amplifier II

10MN Afterburner II

Drone Link Augmentor I

Medium Auxiliary Nano Pump I

Hammerhead II x5
"""
        parser = EFTParser(mock_market_db)
        fit = parser.parse(eft)

        # Verify each section got the right module
        assert len(fit.low_slots) == 1
        assert fit.low_slots[0].type_name == "Drone Damage Amplifier II"

        assert len(fit.mid_slots) == 1
        assert fit.mid_slots[0].type_name == "10MN Afterburner II"

        assert len(fit.high_slots) == 1
        assert fit.high_slots[0].type_name == "Drone Link Augmentor I"

        assert len(fit.rigs) == 1
        assert fit.rigs[0].type_name == "Medium Auxiliary Nano Pump I"

        assert len(fit.drones) == 1
        assert fit.drones[0].type_name == "Hammerhead II"


# =============================================================================
# Type Resolution Error Tests
# =============================================================================


class TestTypeResolutionError:
    """Tests for TypeResolutionError details."""

    def test_error_includes_type_name(self, mock_market_db):
        """Test that error includes the unknown type name."""
        eft = """[Vexor, Test]
Unknown Module ABC
"""
        parser = EFTParser(mock_market_db)
        with pytest.raises(TypeResolutionError) as exc_info:
            parser.parse(eft)

        assert exc_info.value.type_name == "Unknown Module ABC"
        assert "Unknown type: Unknown Module ABC" in str(exc_info.value)

    def test_error_line_number_on_header(self, mock_market_db):
        """Test that header errors include line number."""
        eft = """Malformed Header No Brackets
Module
"""
        parser = EFTParser(mock_market_db)
        with pytest.raises(EFTParseError) as exc_info:
            parser.parse(eft)

        assert exc_info.value.line_number == 1


# =============================================================================
# ParseSection Enum Tests
# =============================================================================


class TestParseSectionEnum:
    """Tests for ParseSection enumeration."""

    def test_all_sections_defined(self):
        """Test that all expected sections are defined."""
        expected = [
            "HEADER",
            "LOW_SLOTS",
            "MID_SLOTS",
            "HIGH_SLOTS",
            "RIGS",
            "SUBSYSTEMS",
            "DRONES",
            "CARGO",
        ]

        for section_name in expected:
            assert hasattr(ParseSection, section_name)
