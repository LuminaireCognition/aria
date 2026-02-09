"""
Tests for loyalty command module.

Tests LP balance tracking and LP store browsing.
"""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.commands.loyalty import cmd_lp, cmd_lp_analyze, cmd_lp_offers


class TestLPCommand:
    """Tests for cmd_lp (LP balance)."""

    def test_lp_no_credentials(self, empty_args):
        """Test behavior when credentials are missing."""
        with patch("aria_esi.commands.loyalty.get_authenticated_client") as mock_auth:
            from aria_esi.core import CredentialsError

            mock_auth.side_effect = CredentialsError("no_credentials", "No credentials found")

            result = cmd_lp(empty_args)

            assert result["error"] == "credentials_error"

    def test_lp_empty_balance(self, empty_args, mock_authenticated_client):
        """Test behavior when no LP balances exist."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = []

        with patch("aria_esi.commands.loyalty.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.loyalty.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = MagicMock()

                result = cmd_lp(empty_args)

                assert "error" not in result
                assert result["total_lp"] == 0
                assert result["corporation_count"] == 0
                assert "No LP balances" in result.get("message", "")

    def test_lp_success(
        self, empty_args, mock_authenticated_client, mock_loyalty_points_response
    ):
        """Test successful LP balance retrieval."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = mock_loyalty_points_response

        mock_public = MagicMock()
        mock_public.get_corporation_info.return_value = {"name": "Test Corp"}

        with patch("aria_esi.commands.loyalty.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.loyalty.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_lp(empty_args)

                assert "error" not in result
                assert result["total_lp"] == 75000  # 50000 + 25000
                assert result["corporation_count"] == 2
                assert len(result["balances"]) == 2

    def test_lp_sorted_by_amount(self, empty_args, mock_authenticated_client):
        """Test that balances are sorted by LP amount descending."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = [
            {"corporation_id": 1000125, "loyalty_points": 1000},
            {"corporation_id": 1000182, "loyalty_points": 50000},
            {"corporation_id": 1000120, "loyalty_points": 25000},
        ]

        mock_public = MagicMock()
        mock_public.get_corporation_info.return_value = {"name": "Test Corp"}

        with patch("aria_esi.commands.loyalty.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.loyalty.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_lp(empty_args)

                balances = result["balances"]
                assert balances[0]["loyalty_points"] == 50000
                assert balances[1]["loyalty_points"] == 25000
                assert balances[2]["loyalty_points"] == 1000


class TestLPOffersCommand:
    """Tests for cmd_lp_offers."""

    @pytest.fixture
    def offers_args(self):
        """Create args for LP offers lookup."""
        args = argparse.Namespace()
        args.corporation = "Federation Navy"
        args.search = None
        args.affordable = False
        args.max_lp = None
        return args

    def test_lp_offers_missing_corporation(self):
        """Test when corporation argument is missing."""
        args = argparse.Namespace()
        args.corporation = None
        args.search = None
        args.affordable = False
        args.max_lp = None

        result = cmd_lp_offers(args)

        assert result["error"] == "missing_argument"

    def test_lp_offers_corporation_not_found(self, offers_args):
        """Test when corporation cannot be resolved."""
        mock_public = MagicMock()
        mock_public.get_corporation_info.return_value = None
        mock_public.resolve_corporation.return_value = (None, None)

        with patch("aria_esi.commands.loyalty.ESIClient") as mock_public_cls:
            mock_public_cls.return_value = mock_public

            offers_args.corporation = "NonexistentCorp12345"
            result = cmd_lp_offers(offers_args)

            assert result["error"] == "corporation_not_found"

    def test_lp_offers_success(self, offers_args):
        """Test successful LP offers retrieval."""
        mock_public = MagicMock()
        mock_public.get_corporation_info.return_value = {"name": "Federation Navy"}
        mock_public.resolve_corporation.return_value = (1000120, "Federation Navy")
        mock_public.get.return_value = [
            {
                "offer_id": 1,
                "type_id": 17703,
                "quantity": 1,
                "lp_cost": 50000,
                "isk_cost": 10000000,
                "required_items": [],
            },
            {
                "offer_id": 2,
                "type_id": 17938,
                "quantity": 1,
                "lp_cost": 125000,
                "isk_cost": 25000000,
                "required_items": [{"type_id": 34, "quantity": 1000}],
            },
        ]
        mock_public.get_dict_safe.return_value = {"name": "Test Item"}

        with patch("aria_esi.commands.loyalty.ESIClient") as mock_public_cls:
            mock_public_cls.return_value = mock_public

            result = cmd_lp_offers(offers_args)

            assert "error" not in result
            assert result["corporation_id"] == 1000120
            assert result["total_offers"] == 2
            assert len(result["offers"]) == 2

    def test_lp_offers_search_filter(self, offers_args):
        """Test LP offers with search filter."""
        offers_args.search = "Navy"

        mock_public = MagicMock()
        mock_public.get_corporation_info.return_value = {"name": "Federation Navy"}
        mock_public.resolve_corporation.return_value = (1000120, "Federation Navy")
        mock_public.get.return_value = [
            {"offer_id": 1, "type_id": 17703, "quantity": 1, "lp_cost": 50000, "isk_cost": 10000000},
            {"offer_id": 2, "type_id": 17938, "quantity": 1, "lp_cost": 125000, "isk_cost": 25000000},
        ]

        def get_dict_safe_impl(path):
            if "17703" in path:
                return {"name": "Federation Navy Comet"}
            return {"name": "Some Other Item"}

        mock_public.get_dict_safe.side_effect = get_dict_safe_impl

        with patch("aria_esi.commands.loyalty.ESIClient") as mock_public_cls:
            mock_public_cls.return_value = mock_public

            result = cmd_lp_offers(offers_args)

            assert "error" not in result
            # Only matching item should be in result
            assert result["filtered_count"] == 1

    def test_lp_offers_known_shortcut(self, offers_args):
        """Test that known shortcuts work."""
        offers_args.corporation = "fed navy"  # Known shortcut

        mock_public = MagicMock()
        mock_public.get_corporation_info.return_value = {"name": "Federation Navy"}
        mock_public.get.return_value = []

        with patch("aria_esi.commands.loyalty.ESIClient") as mock_public_cls:
            mock_public_cls.return_value = mock_public

            result = cmd_lp_offers(offers_args)

            assert "error" not in result
            assert result["corporation_id"] == 1000120  # Federation Navy ID


class TestLPAnalyzeCommand:
    """Tests for cmd_lp_analyze."""

    @pytest.fixture
    def analyze_args(self):
        """Create args for LP analyze."""
        args = argparse.Namespace()
        args.corporation = "Federation Navy"
        return args

    def test_lp_analyze_missing_corporation(self):
        """Test when corporation argument is missing."""
        args = argparse.Namespace()
        args.corporation = None

        result = cmd_lp_analyze(args)

        assert result["error"] == "missing_argument"

    def test_lp_analyze_success(self, analyze_args):
        """Test successful LP store analysis."""
        mock_public = MagicMock()
        mock_public.get_corporation_info.return_value = {"name": "Federation Navy"}
        mock_public.resolve_corporation.return_value = (1000120, "Federation Navy")
        mock_public.get.return_value = [
            # Self-sufficient (no required items)
            {"offer_id": 1, "type_id": 17703, "quantity": 1, "lp_cost": 50000, "isk_cost": 10000000},
            # Requires items
            {
                "offer_id": 2,
                "type_id": 17938,
                "quantity": 1,
                "lp_cost": 125000,
                "isk_cost": 25000000,
                "required_items": [{"type_id": 34, "quantity": 1000}],
            },
        ]
        mock_public.get_dict_safe.return_value = {"name": "Test Item", "group_id": 25}

        with patch("aria_esi.commands.loyalty.ESIClient") as mock_public_cls:
            mock_public_cls.return_value = mock_public

            result = cmd_lp_analyze(analyze_args)

            assert "error" not in result
            assert result["analysis"]["total_offers"] == 2
            assert result["analysis"]["lp_isk_only"] == 1
            assert result["analysis"]["requires_items"] == 1
            assert len(result["self_sufficient_offers"]) == 1
