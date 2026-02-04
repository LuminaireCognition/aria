"""
Tests for character command module.

Tests profile, location, and standings commands.
"""

from unittest.mock import MagicMock, patch

from aria_esi.commands.character import cmd_location, cmd_profile, cmd_standings


class TestProfileCommand:
    """Tests for cmd_profile."""

    def test_profile_no_credentials(self, empty_args):
        """Test behavior when credentials are missing."""
        with patch("aria_esi.commands.character.get_authenticated_client") as mock_auth:
            from aria_esi.core import CredentialsError

            mock_auth.side_effect = CredentialsError("no_credentials", "No credentials found")

            result = cmd_profile(empty_args)

            assert result["error"] == "credentials_error"
            assert "query_timestamp" in result

    def test_profile_success(
        self, empty_args, mock_authenticated_client, mock_character_info, mock_standings_response
    ):
        """Test successful profile retrieval."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = mock_standings_response

        mock_public = MagicMock()
        mock_public.get_dict_safe.return_value = mock_character_info

        with patch("aria_esi.commands.character.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.character.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_profile(empty_args)

                assert "error" not in result
                assert result["volatility"] == "semi_stable"
                assert "character" in result
                assert "standings" in result

    def test_profile_standings_error_graceful(
        self, empty_args, mock_authenticated_client, mock_character_info
    ):
        """Test profile still works if standings fetch fails."""
        mock_client, mock_creds = mock_authenticated_client

        from aria_esi.core import ESIError

        mock_client.get.side_effect = ESIError("Standings error", 500)

        mock_public = MagicMock()
        mock_public.get_dict_safe.return_value = mock_character_info

        with patch("aria_esi.commands.character.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.character.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_profile(empty_args)

                # Should succeed but with empty standings
                assert "error" not in result
                assert result["standings"] == []


class TestLocationCommand:
    """Tests for cmd_location."""

    def test_location_no_credentials(self, empty_args):
        """Test behavior when credentials are missing."""
        with patch("aria_esi.commands.character.get_authenticated_client") as mock_auth:
            from aria_esi.core import CredentialsError

            mock_auth.side_effect = CredentialsError("no_credentials", "No credentials found")

            result = cmd_location(empty_args)

            assert result["error"] == "credentials_error"
            assert "query_timestamp" in result

    def test_location_success_docked(
        self,
        empty_args,
        mock_authenticated_client,
        mock_location_response,
        mock_ship_response,
        mock_system_info_jita,
        mock_station_info,
        mock_type_info_rifter,
    ):
        """Test successful location retrieval when docked."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get_dict.side_effect = [mock_location_response, mock_ship_response]

        mock_public = MagicMock()

        def get_dict_safe_impl(path):
            if "systems" in path:
                return mock_system_info_jita
            elif "stations" in path:
                return mock_station_info
            elif "types" in path:
                return mock_type_info_rifter
            return {}

        mock_public.get_dict_safe.side_effect = get_dict_safe_impl

        with patch("aria_esi.commands.character.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.character.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_location(empty_args)

                assert "error" not in result
                assert result["volatility"] == "volatile"
                assert result["system"] == "Jita"
                assert result["docked"] is True
                assert "Jita" in result["station"]

    def test_location_success_in_space(
        self,
        empty_args,
        mock_authenticated_client,
        mock_ship_response,
        mock_system_info_jita,
        mock_type_info_rifter,
    ):
        """Test successful location retrieval when in space."""
        mock_client, mock_creds = mock_authenticated_client
        # In space - no station_id
        mock_client.get_dict.side_effect = [
            {"solar_system_id": 30000142},  # No station
            mock_ship_response,
        ]

        mock_public = MagicMock()

        def get_dict_safe_impl(path):
            if "systems" in path:
                return mock_system_info_jita
            elif "types" in path:
                return mock_type_info_rifter
            return {}

        mock_public.get_dict_safe.side_effect = get_dict_safe_impl

        with patch("aria_esi.commands.character.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.character.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_location(empty_args)

                assert "error" not in result
                assert result["system"] == "Jita"
                assert result["docked"] is False
                assert result["station"] == ""

    def test_location_esi_error(self, empty_args, mock_authenticated_client):
        """Test handling of ESI location error."""
        mock_client, mock_creds = mock_authenticated_client

        from aria_esi.core import ESIError

        mock_client.get_dict.side_effect = ESIError("Location error", 500)

        with patch("aria_esi.commands.character.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.character.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = MagicMock()

                result = cmd_location(empty_args)

                assert result["error"] == "location_error"

    def test_location_structure_docked(
        self, empty_args, mock_authenticated_client, mock_ship_response, mock_system_info_jita
    ):
        """Test location when docked in a player structure."""
        mock_client, mock_creds = mock_authenticated_client
        # Docked in structure (structure_id instead of station_id)
        mock_client.get_dict.side_effect = [
            {"solar_system_id": 30000142, "structure_id": 1234567890123},
            mock_ship_response,
        ]

        mock_public = MagicMock()
        mock_public.get_dict_safe.side_effect = lambda p: (
            mock_system_info_jita if "systems" in p else {"name": "Rifter"}
        )

        with patch("aria_esi.commands.character.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.character.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_location(empty_args)

                assert "error" not in result
                assert result["docked"] is True
                assert "Structure" in result["station"]


class TestStandingsCommand:
    """Tests for cmd_standings."""

    def test_standings_no_credentials(self, empty_args):
        """Test behavior when credentials are missing."""
        with patch("aria_esi.commands.character.get_authenticated_client") as mock_auth:
            from aria_esi.core import CredentialsError

            mock_auth.side_effect = CredentialsError("no_credentials", "No credentials found")

            result = cmd_standings(empty_args)

            assert result["error"] == "credentials_error"

    def test_standings_success(
        self, empty_args, mock_authenticated_client, mock_standings_response
    ):
        """Test successful standings retrieval."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get_list.return_value = mock_standings_response

        mock_public = MagicMock()
        # Mock faction lookup
        mock_public.get_list_safe.return_value = [
            {"faction_id": 500001, "name": "Caldari State"}
        ]
        mock_public.get_dict_safe.return_value = {"name": "Test Corp"}

        with patch("aria_esi.commands.character.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.character.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_standings(empty_args)

                assert "error" not in result
                assert result["volatility"] == "semi_stable"
                assert len(result["standings"]) == 3

    def test_standings_sorted_by_value(
        self, empty_args, mock_authenticated_client
    ):
        """Test that standings are sorted by value descending."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get_list.return_value = [
            {"from_id": 1, "from_type": "faction", "standing": -5.0},
            {"from_id": 2, "from_type": "faction", "standing": 10.0},
            {"from_id": 3, "from_type": "faction", "standing": 0.0},
        ]

        mock_public = MagicMock()
        mock_public.get_list_safe.return_value = []
        mock_public.get_dict_safe.return_value = {}

        with patch("aria_esi.commands.character.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.character.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_standings(empty_args)

                assert "error" not in result
                standings = result["standings"]
                assert standings[0]["standing"] == 10.0
                assert standings[1]["standing"] == 0.0
                assert standings[2]["standing"] == -5.0

    def test_standings_esi_error(self, empty_args, mock_authenticated_client):
        """Test handling of ESI standings error."""
        mock_client, mock_creds = mock_authenticated_client

        from aria_esi.core import ESIError

        mock_client.get_list.side_effect = ESIError("Standings error", 500)

        with patch("aria_esi.commands.character.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.character.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = MagicMock()

                result = cmd_standings(empty_args)

                assert result["error"] == "standings_error"
