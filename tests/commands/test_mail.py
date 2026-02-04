"""
Tests for mail command module.

Tests EVE mail reading functionality.
"""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.commands.mail import _strip_html, cmd_mail, cmd_mail_labels, cmd_mail_read


class TestStripHtml:
    """Tests for the HTML stripping utility."""

    def test_strip_html_basic(self):
        """Test stripping basic HTML tags."""
        html = "<p>Hello <b>World</b></p>"
        assert _strip_html(html) == "Hello World"

    def test_strip_html_entities(self):
        """Test decoding HTML entities."""
        html = "&lt;test&gt; &amp; &quot;quoted&quot;"
        assert _strip_html(html) == '<test> & "quoted"'

    def test_strip_html_empty(self):
        """Test with empty input."""
        assert _strip_html("") == ""
        assert _strip_html(None) == ""


class TestMailCommand:
    """Tests for cmd_mail."""

    def test_mail_no_credentials(self, mail_args):
        """Test behavior when credentials are missing."""
        with patch("aria_esi.commands.mail.get_authenticated_client") as mock_auth:
            from aria_esi.core import CredentialsError

            mock_auth.side_effect = CredentialsError("no_credentials", "No credentials found")

            result = cmd_mail(mail_args)

            assert result["error"] == "credentials_error"

    def test_mail_missing_scope(self, mail_args, mock_authenticated_client):
        """Test when mail scope is missing."""
        mock_client, mock_creds = mock_authenticated_client
        mock_creds.scopes = []
        mock_creds.has_scope.side_effect = lambda s: False

        with patch("aria_esi.commands.mail.get_authenticated_client") as mock_auth:
            mock_auth.return_value = (mock_client, mock_creds)

            result = cmd_mail(mail_args)

            assert result["error"] == "scope_not_authorized"
            assert "mail.read_mail" in result["message"]

    def test_mail_empty_inbox(self, mail_args, mock_authenticated_client):
        """Test behavior when inbox is empty."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get_list.return_value = []

        with patch("aria_esi.commands.mail.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.mail.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = MagicMock()

                result = cmd_mail(mail_args)

                assert "error" not in result
                assert result["summary"]["total_shown"] == 0
                assert "No mail found" in result.get("message", "")

    def test_mail_success(
        self, mail_args, mock_authenticated_client, mock_mail_headers_response
    ):
        """Test successful mail listing."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get_list.return_value = mock_mail_headers_response

        mock_public = MagicMock()
        mock_public.get_dict_safe.return_value = {"name": "Test Sender"}

        with patch("aria_esi.commands.mail.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.mail.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_mail(mail_args)

                assert "error" not in result
                assert result["summary"]["total_shown"] == 2
                assert result["summary"]["unread_count"] == 1
                assert len(result["mail"]) == 2

    def test_mail_unread_filter(
        self, mock_authenticated_client, mock_mail_headers_response
    ):
        """Test filtering for unread mail only."""
        args = argparse.Namespace()
        args.unread = True
        args.limit = 50

        mock_client, mock_creds = mock_authenticated_client
        mock_client.get_list.return_value = mock_mail_headers_response

        mock_public = MagicMock()
        mock_public.get_dict_safe.return_value = {"name": "Test Sender"}

        with patch("aria_esi.commands.mail.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.mail.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_mail(args)

                assert "error" not in result
                # Only unread mail should be returned
                for mail in result["mail"]:
                    assert mail["is_read"] is False

    def test_mail_esi_error(self, mail_args, mock_authenticated_client):
        """Test handling of ESI errors."""
        mock_client, mock_creds = mock_authenticated_client

        from aria_esi.core import ESIError

        mock_client.get_list.side_effect = ESIError("Mail error", 500)

        with patch("aria_esi.commands.mail.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.mail.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = MagicMock()

                result = cmd_mail(mail_args)

                assert result["error"] == "esi_error"


class TestMailReadCommand:
    """Tests for cmd_mail_read."""

    @pytest.fixture
    def read_args(self):
        """Create args for reading a specific mail."""
        args = argparse.Namespace()
        args.mail_id = 1001
        return args

    def test_mail_read_missing_id(self):
        """Test when mail ID is not provided."""
        args = argparse.Namespace()
        args.mail_id = None

        result = cmd_mail_read(args)

        assert result["error"] == "missing_argument"

    def test_mail_read_no_credentials(self, read_args):
        """Test behavior when credentials are missing."""
        with patch("aria_esi.commands.mail.get_authenticated_client") as mock_auth:
            from aria_esi.core import CredentialsError

            mock_auth.side_effect = CredentialsError("no_credentials", "No credentials found")

            result = cmd_mail_read(read_args)

            assert result["error"] == "credentials_error"

    def test_mail_read_success(
        self, read_args, mock_authenticated_client, mock_mail_body_response
    ):
        """Test successful mail reading."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get_dict.return_value = mock_mail_body_response

        mock_public = MagicMock()
        mock_public.get_dict_safe.return_value = {"name": "Test Sender"}

        with patch("aria_esi.commands.mail.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.mail.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_mail_read(read_args)

                assert "error" not in result
                assert result["mail"]["mail_id"] == 1001
                assert "body" in result["mail"]
                assert "subject" in result["mail"]

    def test_mail_read_not_found(self, read_args, mock_authenticated_client):
        """Test when mail ID is not found."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get_dict.return_value = None

        with patch("aria_esi.commands.mail.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.mail.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = MagicMock()

                result = cmd_mail_read(read_args)

                assert result["error"] == "not_found"


class TestMailLabelsCommand:
    """Tests for cmd_mail_labels."""

    def test_mail_labels_no_credentials(self, empty_args):
        """Test behavior when credentials are missing."""
        with patch("aria_esi.commands.mail.get_authenticated_client") as mock_auth:
            from aria_esi.core import CredentialsError

            mock_auth.side_effect = CredentialsError("no_credentials", "No credentials found")

            result = cmd_mail_labels(empty_args)

            assert result["error"] == "credentials_error"

    def test_mail_labels_success(self, empty_args, mock_authenticated_client):
        """Test successful labels retrieval."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get_dict.return_value = {
            "total_unread_count": 5,
            "labels": [
                {"label_id": 1, "name": "Inbox", "color": None, "unread_count": 3},
                {"label_id": 2, "name": "Sent", "color": None, "unread_count": 0},
                {"label_id": 8, "name": "Custom", "color": "#FF0000", "unread_count": 2},
            ],
        }

        with patch("aria_esi.commands.mail.get_authenticated_client") as mock_auth:
            mock_auth.return_value = (mock_client, mock_creds)

            result = cmd_mail_labels(empty_args)

            assert "error" not in result
            assert result["total_unread_count"] == 5
            assert len(result["labels"]) == 3
