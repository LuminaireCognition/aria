"""
Tests for corporation command module.

Tests corp info, status, wallet, assets, blueprints, and jobs commands.
"""

import argparse
from unittest.mock import MagicMock, patch

from aria_esi.commands.corporation import (
    cmd_corp_assets,
    cmd_corp_blueprints,
    cmd_corp_help,
    cmd_corp_info,
    cmd_corp_jobs,
    cmd_corp_status,
    cmd_corp_wallet,
)


class TestCorpInfoCommand:
    """Tests for cmd_corp_info."""

    def test_corp_info_own_corporation(
        self, corp_info_args, mock_authenticated_client, mock_corporation_info, mock_character_info
    ):
        """Test fetching own corporation info."""
        mock_client, mock_creds = mock_authenticated_client
        mock_creds.character_id = 12345678

        mock_public = MagicMock()

        def get_dict_safe_impl(path):
            if f"/characters/{mock_creds.character_id}/" in path:
                return mock_character_info
            elif "/corporations/" in path:
                return mock_corporation_info
            return {}

        mock_public.get_dict_safe.side_effect = get_dict_safe_impl

        with patch("aria_esi.commands.corporation.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.corporation.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_corp_info(corp_info_args)

                assert "error" not in result
                assert result["name"] == "Test Corporation"
                assert result["ticker"] == "TST"

    def test_corp_info_by_id(self, mock_corporation_info):
        """Test fetching corporation by ID."""
        args = argparse.Namespace()
        args.target = "98000001"

        mock_public = MagicMock()
        mock_public.get_dict_safe.return_value = mock_corporation_info

        with patch("aria_esi.commands.corporation.ESIClient") as mock_public_cls:
            mock_public_cls.return_value = mock_public

            result = cmd_corp_info(args)

            assert "error" not in result
            assert result["corporation_id"] == 98000001

    def test_corp_info_by_name_search(self, mock_corporation_info):
        """Test fetching corporation by name search."""
        args = argparse.Namespace()
        args.target = "Test Corporation"

        mock_public = MagicMock()
        mock_public.post.return_value = {"corporations": [{"id": 98000001}]}
        mock_public.get_dict_safe.return_value = mock_corporation_info

        with patch("aria_esi.commands.corporation.ESIClient") as mock_public_cls:
            mock_public_cls.return_value = mock_public

            result = cmd_corp_info(args)

            assert "error" not in result
            assert result["corporation_id"] == 98000001

    def test_corp_info_not_found(self):
        """Test when corporation is not found."""
        args = argparse.Namespace()
        args.target = "NonexistentCorp"

        mock_public = MagicMock()
        mock_public.post.return_value = {"corporations": []}

        with patch("aria_esi.commands.corporation.ESIClient") as mock_public_cls:
            mock_public_cls.return_value = mock_public

            result = cmd_corp_info(args)

            assert result["error"] == "not_found"


class TestCorpStatusCommand:
    """Tests for cmd_corp_status."""

    def test_corp_status_no_credentials(self, empty_args):
        """Test behavior when credentials are missing."""
        with patch("aria_esi.commands.corporation.get_authenticated_client") as mock_auth:
            from aria_esi.core import CredentialsError

            mock_auth.side_effect = CredentialsError("no_credentials", "No credentials found")

            result = cmd_corp_status(empty_args)

            assert result["error"] == "credentials_error"

    def test_corp_status_npc_corporation(
        self, empty_args, mock_authenticated_client, mock_character_info
    ):
        """Test behavior when in NPC corporation."""
        mock_client, mock_creds = mock_authenticated_client

        # NPC corp ID (below threshold)
        mock_char_info = mock_character_info.copy()
        mock_char_info["corporation_id"] = 1000125  # NPC corp

        mock_public = MagicMock()
        mock_public.get_dict_safe.return_value = mock_char_info

        with patch("aria_esi.commands.corporation.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.corporation.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_corp_status(empty_args)

                assert result["error"] == "npc_corporation"

    def test_corp_status_success(
        self, empty_args, mock_authenticated_client, mock_character_info, mock_corporation_info
    ):
        """Test successful corp status retrieval."""
        mock_client, mock_creds = mock_authenticated_client

        mock_public = MagicMock()

        def get_dict_safe_impl(path):
            if "/characters/" in path:
                return mock_character_info
            elif "/corporations/" in path:
                return mock_corporation_info
            return {}

        mock_public.get_dict_safe.side_effect = get_dict_safe_impl

        with patch("aria_esi.commands.corporation.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.corporation.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_corp_status(empty_args)

                assert "error" not in result
                assert "corporation" in result
                assert result["corporation"]["name"] == "Test Corporation"


class TestCorpWalletCommand:
    """Tests for cmd_corp_wallet."""

    def test_corp_wallet_missing_scope(self, corp_wallet_args, mock_authenticated_client):
        """Test when wallet scope is missing."""
        mock_client, mock_creds = mock_authenticated_client
        mock_creds.scopes = []  # No scopes
        mock_creds.has_scope.side_effect = lambda s: False

        with patch("aria_esi.commands.corporation.get_authenticated_client") as mock_auth:
            mock_auth.return_value = (mock_client, mock_creds)

            result = cmd_corp_wallet(corp_wallet_args)

            assert result["error"] == "scope_not_authorized"

    def test_corp_wallet_success(
        self,
        corp_wallet_args,
        mock_authenticated_client,
        mock_character_info,
        mock_corp_wallets_response,
    ):
        """Test successful wallet retrieval."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = mock_corp_wallets_response

        mock_public = MagicMock()
        mock_public.get_dict_safe.return_value = mock_character_info

        with patch("aria_esi.commands.corporation.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.corporation.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_corp_wallet(corp_wallet_args)

                assert "error" not in result
                assert result["total_balance"] == 175000000.0
                assert len(result["wallets"]) == 3


class TestCorpAssetsCommand:
    """Tests for cmd_corp_assets."""

    def test_corp_assets_missing_scope(self, corp_assets_args, mock_authenticated_client):
        """Test when assets scope is missing."""
        mock_client, mock_creds = mock_authenticated_client
        mock_creds.scopes = []
        mock_creds.has_scope.side_effect = lambda s: False

        with patch("aria_esi.commands.corporation.get_authenticated_client") as mock_auth:
            mock_auth.return_value = (mock_client, mock_creds)

            result = cmd_corp_assets(corp_assets_args)

            assert result["error"] == "scope_not_authorized"

    def test_corp_assets_success(
        self,
        corp_assets_args,
        mock_authenticated_client,
        mock_character_info,
        mock_corp_assets_response,
        mock_station_info,
    ):
        """Test successful asset retrieval."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = mock_corp_assets_response

        mock_public = MagicMock()

        def get_dict_safe_impl(path):
            if "/characters/" in path:
                return mock_character_info
            elif "/stations/" in path:
                return mock_station_info
            elif "/types/" in path:
                return {"name": "Test Item", "group_id": 25}
            return {}

        mock_public.get_dict_safe.side_effect = get_dict_safe_impl

        with patch("aria_esi.commands.corporation.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.corporation.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_corp_assets(corp_assets_args)

                assert "error" not in result
                assert result["total_items"] == 2


class TestCorpBlueprintsCommand:
    """Tests for cmd_corp_blueprints."""

    def test_corp_blueprints_missing_scope(self, corp_blueprints_args, mock_authenticated_client):
        """Test when blueprints scope is missing."""
        mock_client, mock_creds = mock_authenticated_client
        mock_creds.scopes = []
        mock_creds.has_scope.side_effect = lambda s: False

        with patch("aria_esi.commands.corporation.get_authenticated_client") as mock_auth:
            mock_auth.return_value = (mock_client, mock_creds)

            result = cmd_corp_blueprints(corp_blueprints_args)

            assert result["error"] == "scope_not_authorized"

    def test_corp_blueprints_success(
        self,
        corp_blueprints_args,
        mock_authenticated_client,
        mock_character_info,
        mock_corp_blueprints_response,
    ):
        """Test successful blueprint retrieval."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = mock_corp_blueprints_response

        mock_public = MagicMock()

        def get_dict_safe_impl(path):
            if "/characters/" in path:
                return mock_character_info
            elif "/types/" in path:
                return {"name": "Test Blueprint"}
            return {}

        mock_public.get_dict_safe.side_effect = get_dict_safe_impl

        with patch("aria_esi.commands.corporation.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.corporation.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_corp_blueprints(corp_blueprints_args)

                assert "error" not in result
                assert result["bpo_count"] == 1
                assert result["bpc_count"] == 1


class TestCorpJobsCommand:
    """Tests for cmd_corp_jobs."""

    def test_corp_jobs_missing_scope(self, corp_jobs_args, mock_authenticated_client):
        """Test when industry jobs scope is missing."""
        mock_client, mock_creds = mock_authenticated_client
        mock_creds.scopes = []
        mock_creds.has_scope.side_effect = lambda s: False

        with patch("aria_esi.commands.corporation.get_authenticated_client") as mock_auth:
            mock_auth.return_value = (mock_client, mock_creds)

            result = cmd_corp_jobs(corp_jobs_args)

            assert result["error"] == "scope_not_authorized"

    def test_corp_jobs_success(
        self,
        corp_jobs_args,
        mock_authenticated_client,
        mock_character_info,
        mock_corp_jobs_response,
    ):
        """Test successful jobs retrieval."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = mock_corp_jobs_response

        mock_public = MagicMock()

        def get_dict_safe_impl(path):
            if "/characters/" in path:
                return mock_character_info
            elif "/types/" in path:
                return {"name": "Test Product"}
            return {}

        mock_public.get_dict_safe.side_effect = get_dict_safe_impl

        with patch("aria_esi.commands.corporation.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.corporation.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_corp_jobs(corp_jobs_args)

                assert "error" not in result
                assert result["active_count"] == 1


class TestCorpHelpCommand:
    """Tests for cmd_corp_help."""

    def test_corp_help_returns_help_dict(self, empty_args):
        """Test that help returns expected structure."""
        result = cmd_corp_help(empty_args)

        assert "command" in result
        assert "description" in result
        assert "subcommands" in result
        assert "examples" in result
        assert "status" in result["subcommands"]
        assert "wallet" in result["subcommands"]
