"""
Tests for orders command module.

Tests market order viewing functionality.
"""

import argparse
from unittest.mock import MagicMock, patch

from aria_esi.commands.orders import _format_range, cmd_orders


class TestFormatRange:
    """Tests for the range formatting utility."""

    def test_format_range_station(self):
        """Test station range formatting."""
        assert _format_range("station") == "Station"

    def test_format_range_solarsystem(self):
        """Test solar system range formatting."""
        assert _format_range("solarsystem") == "Solar System"

    def test_format_range_region(self):
        """Test region range formatting."""
        assert _format_range("region") == "Region"

    def test_format_range_numeric(self):
        """Test numeric jump range formatting."""
        assert _format_range("5") == "5 jumps"
        assert _format_range(10) == "10 jumps"

    def test_format_range_unknown(self):
        """Test unknown range formatting."""
        assert _format_range("unknown") == "unknown"


class TestOrdersCommand:
    """Tests for cmd_orders."""

    def test_orders_no_credentials(self, orders_args):
        """Test behavior when credentials are missing."""
        with patch("aria_esi.commands.orders.get_authenticated_client") as mock_auth:
            from aria_esi.core import CredentialsError

            mock_auth.side_effect = CredentialsError("no_credentials", "No credentials found")

            result = cmd_orders(orders_args)

            assert result["error"] == "credentials_error"

    def test_orders_missing_scope(self, orders_args, mock_authenticated_client):
        """Test when market orders scope is missing."""
        mock_client, mock_creds = mock_authenticated_client
        mock_creds.scopes = []
        mock_creds.has_scope.side_effect = lambda s: False

        with patch("aria_esi.commands.orders.get_authenticated_client") as mock_auth:
            mock_auth.return_value = (mock_client, mock_creds)

            result = cmd_orders(orders_args)

            assert result["error"] == "scope_not_authorized"
            assert "read_character_orders" in result["message"]

    def test_orders_empty_list(self, orders_args, mock_authenticated_client):
        """Test behavior when no orders exist."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = []

        with patch("aria_esi.commands.orders.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.orders.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = MagicMock()

                result = cmd_orders(orders_args)

                assert "error" not in result
                assert result["summary"]["active_orders"] == 0
                assert "No market orders" in result.get("message", "")

    def test_orders_success(
        self, orders_args, mock_authenticated_client, mock_orders_response
    ):
        """Test successful order retrieval."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = mock_orders_response

        mock_public = MagicMock()
        mock_public.get_safe.return_value = {"name": "Test Item"}

        with patch("aria_esi.commands.orders.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.orders.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_orders(orders_args)

                assert "error" not in result
                assert result["summary"]["active_orders"] == 2
                assert result["summary"]["buy_orders"] == 1
                assert result["summary"]["sell_orders"] == 1
                assert len(result["orders"]) == 2

    def test_orders_buy_only_filter(self, mock_authenticated_client, mock_orders_response):
        """Test filtering for buy orders only."""
        args = argparse.Namespace()
        args.buy = True
        args.sell = False
        args.history = False
        args.limit = 50

        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = mock_orders_response

        mock_public = MagicMock()
        mock_public.get_safe.return_value = {"name": "Test Item"}

        with patch("aria_esi.commands.orders.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.orders.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_orders(args)

                assert "error" not in result
                # Only buy orders should be returned
                for order in result["orders"]:
                    assert order["is_buy_order"] is True

    def test_orders_sell_only_filter(self, mock_authenticated_client, mock_orders_response):
        """Test filtering for sell orders only."""
        args = argparse.Namespace()
        args.buy = False
        args.sell = True
        args.history = False
        args.limit = 50

        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = mock_orders_response

        mock_public = MagicMock()
        mock_public.get_safe.return_value = {"name": "Test Item"}

        with patch("aria_esi.commands.orders.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.orders.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_orders(args)

                assert "error" not in result
                # Only sell orders should be returned
                for order in result["orders"]:
                    assert order["is_buy_order"] is False

    def test_orders_calculates_fill_percent(self, orders_args, mock_authenticated_client):
        """Test that fill percentage is calculated correctly."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = [
            {
                "order_id": 4001,
                "type_id": 34,
                "location_id": 60003760,
                "region_id": 10000002,
                "price": 5.50,
                "volume_total": 1000,
                "volume_remain": 250,  # 75% filled
                "is_buy_order": False,
                "issued": "2026-01-20T12:00:00Z",
                "duration": 90,
                "range": "station",
            }
        ]

        mock_public = MagicMock()
        mock_public.get_safe.return_value = {"name": "Test Item"}

        with patch("aria_esi.commands.orders.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.orders.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_orders(orders_args)

                assert "error" not in result
                order = result["orders"][0]
                assert order["fill_percent"] == 75.0

    def test_orders_esi_error(self, orders_args, mock_authenticated_client):
        """Test handling of ESI errors."""
        mock_client, mock_creds = mock_authenticated_client

        from aria_esi.core import ESIError

        mock_client.get.side_effect = ESIError("Orders error", 500)

        with patch("aria_esi.commands.orders.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.orders.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = MagicMock()

                result = cmd_orders(orders_args)

                assert result["error"] == "esi_error"

    def test_orders_summary_escrow_and_value(self, orders_args, mock_authenticated_client):
        """Test that summary correctly calculates escrow and sell value."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = [
            {
                "order_id": 4001,
                "type_id": 34,
                "location_id": 60003760,
                "region_id": 10000002,
                "price": 100.00,
                "volume_total": 1000,
                "volume_remain": 500,
                "is_buy_order": False,
                "issued": "2026-01-20T12:00:00Z",
                "duration": 90,
                "range": "station",
            },
            {
                "order_id": 4002,
                "type_id": 35,
                "location_id": 60003760,
                "region_id": 10000002,
                "price": 50.00,
                "volume_total": 2000,
                "volume_remain": 2000,
                "is_buy_order": True,
                "issued": "2026-01-20T12:00:00Z",
                "duration": 90,
                "range": "station",
                "escrow": 100000.0,
            },
        ]

        mock_public = MagicMock()
        mock_public.get_safe.return_value = {"name": "Test Item"}

        with patch("aria_esi.commands.orders.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.orders.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_orders(orders_args)

                assert "error" not in result
                # Sell value: 100 * 500 = 50000
                assert result["summary"]["total_sell_value"] == 50000.0
                # Escrow from buy order
                assert result["summary"]["total_escrow"] == 100000.0
