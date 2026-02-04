"""
Tests for agents_research command module.

Tests research agent partnerships and accumulated RP tracking.
"""

from unittest.mock import MagicMock, patch

from aria_esi.commands.agents_research import cmd_agents_research


class TestAgentsResearchCommand:
    """Tests for cmd_agents_research."""

    def test_agents_research_no_credentials(self, empty_args):
        """Test behavior when credentials are missing."""
        with patch("aria_esi.commands.agents_research.get_authenticated_client") as mock_auth:
            from aria_esi.core import CredentialsError

            mock_auth.side_effect = CredentialsError("no_credentials", "No credentials found")

            result = cmd_agents_research(empty_args)

            assert result["error"] == "credentials_error"
            assert "query_timestamp" in result

    def test_agents_research_missing_scope(self, empty_args, mock_authenticated_client):
        """Test behavior when required scope is missing."""
        mock_client, mock_creds = mock_authenticated_client
        mock_creds.scopes = []  # No scopes
        mock_creds.has_scope.side_effect = lambda s: False

        with patch("aria_esi.commands.agents_research.get_authenticated_client") as mock_auth:
            mock_auth.return_value = (mock_client, mock_creds)

            result = cmd_agents_research(empty_args)

            assert result["error"] == "scope_not_authorized"
            assert "agents_research" in result["message"]

    def test_agents_research_empty_list(self, empty_args, mock_authenticated_client):
        """Test behavior when no research agents are active."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get_list.return_value = []

        with patch("aria_esi.commands.agents_research.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.agents_research.ESIClient") as mock_public:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public.return_value = MagicMock()

                result = cmd_agents_research(empty_args)

                assert "error" not in result
                assert result["summary"]["total_agents"] == 0
                assert result["agents"] == []
                assert "No active research agents" in result.get("message", "")

    def test_agents_research_success(
        self, empty_args, mock_authenticated_client, mock_research_agents_response
    ):
        """Test successful retrieval of research agents."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get_list.return_value = mock_research_agents_response

        mock_public = MagicMock()
        mock_public.get_dict_safe.return_value = {"name": "Mechanical Engineering"}

        with patch("aria_esi.commands.agents_research.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.agents_research.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_agents_research(empty_args)

                assert "error" not in result
                assert result["summary"]["total_agents"] == 2
                assert len(result["agents"]) == 2
                assert result["summary"]["total_daily_rp"] > 0
                assert result["summary"]["total_accumulated_rp"] > 0

    def test_agents_research_calculates_accumulated_rp(
        self, empty_args, mock_authenticated_client
    ):
        """Test that accumulated RP is calculated correctly."""
        mock_client, mock_creds = mock_authenticated_client
        # Single agent with known values
        mock_client.get_list.return_value = [
            {
                "agent_id": 3019003,
                "skill_type_id": 11433,
                "started_at": "2020-01-01T00:00:00Z",  # Long time ago
                "points_per_day": 100.0,
                "remainder_points": 50.0,
            }
        ]

        mock_public = MagicMock()
        mock_public.get_dict_safe.return_value = {"name": "Test Skill"}

        with patch("aria_esi.commands.agents_research.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.agents_research.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_agents_research(empty_args)

                assert "error" not in result
                # Accumulated should be > remainder due to days passed
                agent = result["agents"][0]
                assert agent["accumulated_rp"] > agent["remainder_points"]
                assert agent["days_active"] > 0

    def test_agents_research_esi_error(self, empty_args, mock_authenticated_client):
        """Test handling of ESI errors."""
        mock_client, mock_creds = mock_authenticated_client

        with patch("aria_esi.commands.agents_research.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.agents_research.ESIClient") as mock_public_cls:
                from aria_esi.core import ESIError

                mock_auth.return_value = (mock_client, mock_creds)
                mock_client.get_list.side_effect = ESIError("API error", 500)
                mock_public_cls.return_value = MagicMock()

                result = cmd_agents_research(empty_args)

                assert result["error"] == "esi_error"
                assert "Could not fetch research agents" in result["message"]

    def test_agents_research_sorted_by_accumulated_rp(
        self, empty_args, mock_authenticated_client
    ):
        """Test that agents are sorted by accumulated RP descending."""
        mock_client, mock_creds = mock_authenticated_client
        mock_client.get_list.return_value = [
            {
                "agent_id": 1,
                "skill_type_id": 11433,
                "started_at": "2026-01-01T00:00:00Z",
                "points_per_day": 10.0,
                "remainder_points": 100.0,  # Lower
            },
            {
                "agent_id": 2,
                "skill_type_id": 11442,
                "started_at": "2020-01-01T00:00:00Z",  # Much older
                "points_per_day": 100.0,
                "remainder_points": 1000.0,  # Higher
            },
        ]

        mock_public = MagicMock()
        mock_public.get_dict_safe.return_value = {"name": "Test Skill"}

        with patch("aria_esi.commands.agents_research.get_authenticated_client") as mock_auth:
            with patch("aria_esi.commands.agents_research.ESIClient") as mock_public_cls:
                mock_auth.return_value = (mock_client, mock_creds)
                mock_public_cls.return_value = mock_public

                result = cmd_agents_research(empty_args)

                assert "error" not in result
                agents = result["agents"]
                assert len(agents) == 2
                # Second agent should be first due to higher accumulated RP
                assert agents[0]["agent_id"] == 2
                assert agents[1]["agent_id"] == 1
