"""
Tests for aria_esi command modules

Tests command routing, argument parsing, and basic command behavior.
"""

import argparse
import json
from unittest.mock import MagicMock, patch

import pytest


class TestCommandImports:
    """Tests that all command modules can be imported."""

    def test_import_navigation(self):
        from aria_esi.commands import navigation
        assert hasattr(navigation, 'cmd_route')
        assert hasattr(navigation, 'cmd_activity')
        assert hasattr(navigation, 'register_parsers')

    def test_import_market(self):
        from aria_esi.commands import market
        assert hasattr(market, 'register_parsers')

    def test_import_pilot(self):
        from aria_esi.commands import pilot
        assert hasattr(pilot, 'register_parsers')

    def test_import_character(self):
        from aria_esi.commands import character
        assert hasattr(character, 'register_parsers')

    def test_import_wallet(self):
        from aria_esi.commands import wallet
        assert hasattr(wallet, 'register_parsers')

    def test_import_skills(self):
        from aria_esi.commands import skills
        assert hasattr(skills, 'register_parsers')

    def test_import_killmails(self):
        from aria_esi.commands import killmails
        assert hasattr(killmails, 'cmd_killmails')
        assert hasattr(killmails, 'cmd_killmail_detail')
        assert hasattr(killmails, 'cmd_loss_analysis')

    def test_import_contracts(self):
        from aria_esi.commands import contracts
        assert hasattr(contracts, 'register_parsers')

    def test_import_clones(self):
        from aria_esi.commands import clones
        assert hasattr(clones, 'register_parsers')

    def test_import_mining(self):
        from aria_esi.commands import mining
        assert hasattr(mining, 'register_parsers')

    def test_import_fittings(self):
        from aria_esi.commands import fittings
        assert hasattr(fittings, 'register_parsers')

    def test_import_mail(self):
        from aria_esi.commands import mail
        assert hasattr(mail, 'register_parsers')


class TestParserRegistration:
    """Tests that command parsers are properly registered."""

    def test_parser_build(self):
        """Test that the full parser can be built without errors."""
        from aria_esi.__main__ import build_parser

        parser = build_parser()

        assert parser is not None
        assert isinstance(parser, argparse.ArgumentParser)

    def test_parser_has_subcommands(self):
        from aria_esi.__main__ import build_parser

        parser = build_parser()

        # Parse known commands to verify they exist
        args = parser.parse_args(["help"])
        assert args.command == "help"

        args = parser.parse_args(["route", "Jita", "Amarr"])
        assert args.command == "route"
        assert args.origin == "Jita"
        assert args.destination == "Amarr"

    def test_route_parser_flags(self):
        from aria_esi.__main__ import build_parser

        parser = build_parser()

        # Test default flag
        args = parser.parse_args(["route", "A", "B"])
        assert args.route_flag == "shortest"

        # Test --safe flag
        args = parser.parse_args(["route", "A", "B", "--safe"])
        assert args.route_flag == "secure"

        # Test --risky flag
        args = parser.parse_args(["route", "A", "B", "--risky"])
        assert args.route_flag == "insecure"

    def test_killmails_parser_flags(self):
        from aria_esi.__main__ import build_parser

        parser = build_parser()

        args = parser.parse_args(["killmails"])
        assert args.limit == 10
        assert args.losses is False
        assert args.kills is False

        args = parser.parse_args(["killmails", "--losses", "--limit", "5"])
        assert args.losses is True
        assert args.limit == 5


class TestNavigationCommands:
    """Tests for navigation command implementations.

    Note: Route commands now use local UniverseGraph instead of ESI.
    Tests mock load_universe_graph to control graph data.
    """

    @pytest.fixture
    def mock_universe(self):
        """Create a mock UniverseGraph for testing."""
        import numpy as np

        mock = MagicMock()

        # System name mappings
        mock.name_lookup = {
            "jita": "Jita",
            "amarr": "Amarr",
            "dodixie": "Dodixie",
        }
        mock.idx_to_name = {
            0: "Jita",
            1: "Amarr",
            2: "Dodixie",
            3: "Perimeter",
        }
        mock.name_to_idx = {
            "Jita": 0,
            "Amarr": 1,
            "Dodixie": 2,
            "Perimeter": 3,
        }

        # Security values
        mock.security = np.array([0.95, 0.90, 0.87, 0.90], dtype=np.float32)

        # Mock resolve_name method
        def resolve_name(name):
            canonical = mock.name_lookup.get(name.lower())
            if canonical:
                return mock.name_to_idx.get(canonical)
            return None
        mock.resolve_name = MagicMock(side_effect=resolve_name)

        # Mock get_system_id
        mock.get_system_id = MagicMock(side_effect=lambda idx: 30000142 + idx)

        # Mock get_constellation_name and get_region_name
        mock.get_constellation_name = MagicMock(return_value="Kimotoro")
        mock.get_region_name = MagicMock(return_value="The Forge")

        # Mock graph for pathfinding
        mock.graph = MagicMock()
        # Default: return a 3-system path [0, 3, 1] (Jita -> Perimeter -> Amarr)
        mock.graph.get_shortest_paths = MagicMock(return_value=[[0, 3, 1]])
        mock.graph.es = []  # No edges for weight computation

        return mock

    def test_route_same_system(self, route_args, mock_universe):
        from aria_esi.commands.navigation import cmd_route

        route_args.origin = "Jita"
        route_args.destination = "Jita"

        with patch('aria_esi.commands.navigation.load_universe_graph', return_value=mock_universe):
            result = cmd_route(route_args)

        assert result.get("error") == "same_system"
        assert "query_timestamp" in result

    def test_route_system_not_found(self, route_args, mock_universe):
        from aria_esi.commands.navigation import cmd_route

        route_args.origin = "NonexistentSystem"
        route_args.destination = "Jita"

        with patch('aria_esi.commands.navigation.load_universe_graph', return_value=mock_universe):
            result = cmd_route(route_args)

        assert result.get("error") == "system_not_found"
        assert "NonexistentSystem" in result.get("message", "")

    def test_route_success(self, route_args, mock_universe):
        from aria_esi.commands.navigation import cmd_route

        route_args.origin = "Jita"
        route_args.destination = "Amarr"

        with patch('aria_esi.commands.navigation.load_universe_graph', return_value=mock_universe):
            result = cmd_route(route_args)

        assert "error" not in result
        assert result.get("total_jumps") == 2  # 3 systems = 2 jumps
        assert "security_summary" in result
        assert "query_timestamp" in result

    def test_route_graph_not_available(self, route_args):
        from aria_esi.commands.navigation import cmd_route
        from aria_esi.universe import UniverseBuildError

        with patch('aria_esi.commands.navigation.load_universe_graph',
                   side_effect=UniverseBuildError("Graph not found")):
            result = cmd_route(route_args)

        assert result.get("error") == "graph_not_available"
        assert "query_timestamp" in result

    def test_activity_command_system_not_found(self):
        from aria_esi.commands.navigation import cmd_activity
        from aria_esi.core import ESIClient

        args = argparse.Namespace()
        args.system = "NonexistentSystem"

        with patch.object(ESIClient, 'resolve_names', return_value={}):
            result = cmd_activity(args)

        assert result.get("error") == "system_not_found"

    def test_activity_command_uses_cache(self):
        """Test that cmd_activity uses cached data for O(1) lookups."""
        import aria_esi.commands.navigation as nav_module
        from aria_esi.commands.navigation import cmd_activity
        from aria_esi.core import ESIClient

        # Reset the module-level cache
        nav_module._activity_cache = None

        args = argparse.Namespace()
        args.system = "Jita"

        # Mock ESI responses
        mock_kills_data = [
            {"system_id": 30000142, "ship_kills": 5, "pod_kills": 2, "npc_kills": 100}
        ]
        mock_jumps_data = [
            {"system_id": 30000142, "ship_jumps": 500}
        ]
        mock_system_info = {"security_status": 0.95}

        with patch.object(ESIClient, 'resolve_names', return_value={"systems": [{"id": 30000142, "name": "Jita"}]}):
            with patch.object(ESIClient, 'get_safe') as mock_get_safe:
                # First call returns system info, subsequent calls return kills/jumps
                def get_safe_side_effect(endpoint, default=None):
                    if "systems/30000142" in endpoint:
                        return mock_system_info
                    elif "system_kills" in endpoint:
                        return mock_kills_data
                    elif "system_jumps" in endpoint:
                        return mock_jumps_data
                    return default

                mock_get_safe.side_effect = get_safe_side_effect
                result = cmd_activity(args)

        # Verify result has correct activity data
        assert "error" not in result
        assert result["activity"]["ship_kills"] == 5
        assert result["activity"]["pod_kills"] == 2
        assert result["activity"]["npc_kills"] == 100
        assert result["activity"]["jumps"] == 500

        # Clean up
        nav_module._activity_cache = None

    def test_activity_cache_reuses_data(self):
        """Test that ActivityCache doesn't refetch within TTL."""

        from aria_esi.commands.navigation import ActivityCache
        from aria_esi.core import ESIClient

        cache = ActivityCache()
        mock_client = MagicMock(spec=ESIClient)

        # Mock ESI responses
        mock_client.get_safe.side_effect = [
            # First refresh_kills call
            [{"system_id": 30000142, "ship_kills": 5, "pod_kills": 2, "npc_kills": 100}],
            # First refresh_jumps call
            [{"system_id": 30000142, "ship_jumps": 500}],
        ]

        # First call - should fetch from ESI
        result1 = cache.get_activity(30000142, mock_client)
        assert result1.ship_kills == 5
        assert result1.ship_jumps == 500

        # Verify ESI was called twice (kills + jumps)
        assert mock_client.get_safe.call_count == 2

        # Second call within TTL - should NOT call ESI again
        result2 = cache.get_activity(30000142, mock_client)
        assert result2.ship_kills == 5
        assert result2.ship_jumps == 500

        # Call count should still be 2 (no new calls)
        assert mock_client.get_safe.call_count == 2

    def test_activity_cache_o1_lookup(self):
        """Test that cache provides O(1) lookups after initial fetch."""
        from aria_esi.commands.navigation import ActivityCache
        from aria_esi.core import ESIClient

        cache = ActivityCache()
        mock_client = MagicMock(spec=ESIClient)

        # Simulate 1000 systems worth of data
        kills_data = [
            {"system_id": 30000000 + i, "ship_kills": i, "pod_kills": 0, "npc_kills": 0}
            for i in range(1000)
        ]
        jumps_data = [
            {"system_id": 30000000 + i, "ship_jumps": i * 10}
            for i in range(1000)
        ]

        mock_client.get_safe.side_effect = [kills_data, jumps_data]

        # First call fetches and caches
        result = cache.get_activity(30000500, mock_client)
        assert result.ship_kills == 500
        assert result.ship_jumps == 5000

        # Subsequent lookups should not call ESI
        for system_id in [30000100, 30000200, 30000300]:
            result = cache.get_activity(system_id, mock_client)
            expected_kills = system_id - 30000000
            assert result.ship_kills == expected_kills

        # Only 2 ESI calls total (initial kills + jumps fetch)
        assert mock_client.get_safe.call_count == 2

    def test_activity_cache_handles_missing_systems(self):
        """Test that cache returns zeros for systems with no activity."""
        from aria_esi.commands.navigation import ActivityCache
        from aria_esi.core import ESIClient

        cache = ActivityCache()
        mock_client = MagicMock(spec=ESIClient)

        # Only Jita has activity
        mock_client.get_safe.side_effect = [
            [{"system_id": 30000142, "ship_kills": 5, "pod_kills": 2, "npc_kills": 100}],
            [{"system_id": 30000142, "ship_jumps": 500}],
        ]

        # Query a system with no activity data
        result = cache.get_activity(99999999, mock_client)

        # Should return zeros, not error
        assert result.ship_kills == 0
        assert result.pod_kills == 0
        assert result.npc_kills == 0
        assert result.ship_jumps == 0


class TestHelpCommand:
    """Tests for help command."""

    def test_cmd_help(self):
        from aria_esi.__main__ import cmd_help

        args = argparse.Namespace()

        # Should print help and return empty dict
        result = cmd_help(args)

        assert result == {}


class TestTestCoreCommand:
    """Tests for test-core diagnostic command."""

    def test_cmd_test_core_basic(self):
        from aria_esi.__main__ import cmd_test_core

        args = argparse.Namespace()

        with patch('aria_esi.core.ESIClient') as MockClient:
            mock_instance = MagicMock()
            mock_instance.get_safe.return_value = {"name": "Jita"}
            MockClient.return_value = mock_instance

            with patch('aria_esi.core.Credentials.resolve', return_value=None):
                result = cmd_test_core(args)

        assert "query_timestamp" in result
        assert "checks" in result
        assert result["status"] in ["passed", "failed"]


class TestOutputFunctions:
    """Tests for output helper functions."""

    def test_output_json(self, capsys):
        from aria_esi.__main__ import output_json

        data = {"test": "value", "number": 42}
        output_json(data)

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == data

    def test_output_error(self):
        from aria_esi.__main__ import output_error

        with pytest.raises(SystemExit) as exc_info:
            output_error("Test error", exit_code=1)

        assert exc_info.value.code == 1


class TestMainEntryPoint:
    """Tests for main() entry point."""

    def test_main_no_command_shows_help(self, monkeypatch):
        from aria_esi.__main__ import main

        monkeypatch.setattr('sys.argv', ['aria-esi'])

        result = main()

        assert result == 0

    def test_main_unknown_command(self, monkeypatch):
        from aria_esi.__main__ import main

        monkeypatch.setattr('sys.argv', ['aria-esi', 'unknowncommand'])

        with pytest.raises(SystemExit):
            main()


class TestKillmailsCommand:
    """Tests for killmails commands."""

    def test_killmails_no_credentials(self, killmails_args):
        from aria_esi.commands.killmails import cmd_killmails
        from aria_esi.core import CredentialsError

        with patch('aria_esi.commands.killmails.get_authenticated_client') as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")

            result = cmd_killmails(killmails_args)

        assert result.get("error") == "credentials_error"

    def test_killmails_missing_scope(self, killmails_args, mock_credentials_data):
        from aria_esi.commands.killmails import cmd_killmails
        from aria_esi.core import Credentials, ESIClient

        # Create credentials without killmail scope
        mock_creds = MagicMock(spec=Credentials)
        mock_creds.character_id = 12345678
        mock_creds.access_token = "token"
        mock_creds.has_scope.return_value = False  # Missing scope

        mock_client = MagicMock(spec=ESIClient)

        with patch('aria_esi.commands.killmails.get_authenticated_client', return_value=(mock_client, mock_creds)):
            with patch('aria_esi.commands.killmails.ESIClient', return_value=mock_client):
                result = cmd_killmails(killmails_args)

        assert result.get("error") == "scope_not_authorized"

    def test_loss_analysis_no_losses(self, empty_args):
        from aria_esi.commands.killmails import cmd_loss_analysis
        from aria_esi.core import Credentials, ESIClient

        mock_creds = MagicMock(spec=Credentials)
        mock_creds.character_id = 12345678
        mock_creds.access_token = "token"
        mock_creds.has_scope.return_value = True

        mock_client = MagicMock(spec=ESIClient)
        mock_client.get.return_value = []  # No killmails

        with patch('aria_esi.commands.killmails.get_authenticated_client', return_value=(mock_client, mock_creds)):
            with patch('aria_esi.commands.killmails.ESIClient', return_value=mock_client):
                result = cmd_loss_analysis(empty_args)

        assert "No recent losses" in result.get("message", "")


class TestPilotCommands:
    """Tests for pilot command implementations."""

    def test_cmd_pilot_self_no_credentials(self, empty_args):
        """Test self query without credentials."""
        from aria_esi.commands.pilot import cmd_pilot

        empty_args.target = "me"

        with patch('aria_esi.commands.pilot.get_credentials', return_value=None):
            with patch('aria_esi.commands.pilot.get_pilot_directory', return_value=None):
                result = cmd_pilot(empty_args)

        assert "query_timestamp" in result
        assert result.get("query_type") == "self"
        assert result.get("esi_configured") is False

    def test_cmd_pilot_public_not_found(self, empty_args):
        """Test public lookup for non-existent pilot."""
        from aria_esi.commands.pilot import cmd_pilot

        empty_args.target = "NonexistentPilot123"

        with patch('aria_esi.commands.pilot.ESIClient') as MockESIClient:
            mock_client = MockESIClient.return_value
            mock_client.resolve_character.return_value = (None, None)
            result = cmd_pilot(empty_args)

        assert result.get("error") == "not_found"
        assert "NonexistentPilot123" in result.get("message", "")
        assert "query_timestamp" in result

    def test_cmd_pilot_public_success(self, empty_args, mock_character_response):
        """Test successful public pilot lookup."""
        from aria_esi.commands.pilot import cmd_pilot

        empty_args.target = "Test Pilot"

        with patch('aria_esi.commands.pilot.ESIClient') as MockESIClient:
            mock_client = MockESIClient.return_value
            mock_client.resolve_character.return_value = (12345678, "Test Pilot")
            mock_client.get_character_info.return_value = mock_character_response
            mock_client.get_corporation_info.return_value = {
                "name": "Test Corp",
                "ticker": "TEST"
            }
            result = cmd_pilot(empty_args)

        assert result.get("query_type") == "public"
        assert result.get("public_data_only") is True
        assert result["character"]["name"] == "Test Pilot"
        assert "query_timestamp" in result

    def test_cmd_pilot_by_id(self, empty_args, mock_character_response):
        """Test pilot lookup by character ID."""
        from aria_esi.commands.pilot import cmd_pilot

        empty_args.target = "12345678"

        with patch('aria_esi.commands.pilot.ESIClient') as MockESIClient:
            mock_client = MockESIClient.return_value
            mock_client.get_character_info.return_value = mock_character_response
            mock_client.get_corporation_info.return_value = {
                "name": "Test Corp",
                "ticker": "TEST"
            }
            result = cmd_pilot(empty_args)

        assert result.get("query_type") == "public"
        assert result["character"]["id"] == 12345678

    def test_parse_profile_config(self, tmp_path):
        """Test profile.md parsing."""
        from aria_esi.commands.pilot import _parse_profile_config

        profile_content = """# Pilot Profile

**Character Name:** Test Capsuleer
**Primary Faction:** Gallente
**EVE Experience:** veteran
**RP Level:** moderate
**Module Tier:** t2

## Operational Constraints

```yaml
market_access: false
self_sufficient: true
```
"""
        profile_path = tmp_path / "profile.md"
        profile_path.write_text(profile_content)

        config = _parse_profile_config(profile_path)

        assert config["character_name"] == "Test Capsuleer"
        assert config["primary_faction"] == "Gallente"
        assert config["eve_experience"] == "veteran"
        assert config["rp_level"] == "moderate"
        assert config["constraints"]["market_access"] is False
        assert config["constraints"]["self_sufficient"] is True


class TestWalletCommands:
    """Tests for wallet command implementations."""

    def test_cmd_wallet_no_credentials(self, empty_args):
        """Test wallet command without credentials."""
        from aria_esi.commands.wallet import cmd_wallet
        from aria_esi.core import CredentialsError

        with patch('aria_esi.commands.wallet.get_authenticated_client') as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_wallet(empty_args)

        assert result.get("error") == "credentials_error"
        assert "query_timestamp" in result

    def test_cmd_wallet_success(self, empty_args, mock_wallet_response):
        """Test successful wallet balance fetch."""
        from aria_esi.commands.wallet import cmd_wallet
        from aria_esi.core import Credentials, ESIClient

        mock_creds = MagicMock(spec=Credentials)
        mock_creds.character_id = 12345678

        mock_client = MagicMock(spec=ESIClient)
        mock_client.get.return_value = mock_wallet_response

        with patch('aria_esi.commands.wallet.get_authenticated_client', return_value=(mock_client, mock_creds)):
            result = cmd_wallet(empty_args)

        assert result.get("balance_isk") == mock_wallet_response
        assert result.get("volatility") == "volatile"
        assert "query_timestamp" in result

    def test_cmd_wallet_journal_no_credentials(self, empty_args):
        """Test wallet journal without credentials."""
        from aria_esi.commands.wallet import cmd_wallet_journal
        from aria_esi.core import CredentialsError

        empty_args.days = 7
        empty_args.filter_type = None

        with patch('aria_esi.commands.wallet.get_authenticated_client') as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_wallet_journal(empty_args)

        assert result.get("error") == "credentials_error"

    def test_cmd_wallet_journal_success(self, empty_args):
        """Test successful wallet journal fetch."""
        from datetime import datetime, timezone

        from aria_esi.commands.wallet import cmd_wallet_journal
        from aria_esi.core import Credentials, ESIClient

        empty_args.days = 7
        empty_args.filter_type = None

        mock_creds = MagicMock(spec=Credentials)
        mock_creds.character_id = 12345678

        mock_client = MagicMock(spec=ESIClient)

        # Mock journal entries
        now = datetime.now(timezone.utc)
        mock_journal = [
            {
                "id": 1,
                "date": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ref_type": "bounty_prizes",
                "amount": 1000000,
                "balance": 5000000,
                "description": "Test bounty"
            },
            {
                "id": 2,
                "date": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ref_type": "market_escrow",
                "amount": -500000,
                "balance": 4500000,
                "description": "Market purchase"
            }
        ]
        mock_transactions = []

        mock_client.get.side_effect = [mock_journal, mock_transactions]

        with patch('aria_esi.commands.wallet.get_authenticated_client', return_value=(mock_client, mock_creds)):
            with patch('aria_esi.commands.wallet.ESIClient') as MockPublicClient:
                MockPublicClient.return_value = MagicMock()
                result = cmd_wallet_journal(empty_args)

        assert "summary" in result
        assert result["summary"]["total_income"] == 1000000
        assert result["summary"]["total_expenses"] == 500000
        assert result["summary"]["net_change"] == 500000
        assert "query_timestamp" in result

    def test_cmd_wallet_journal_with_filter(self, empty_args):
        """Test wallet journal with type filter."""
        from datetime import datetime, timezone

        from aria_esi.commands.wallet import cmd_wallet_journal
        from aria_esi.core import Credentials, ESIClient

        empty_args.days = 7
        empty_args.filter_type = "bounty"

        mock_creds = MagicMock(spec=Credentials)
        mock_creds.character_id = 12345678

        mock_client = MagicMock(spec=ESIClient)

        now = datetime.now(timezone.utc)
        mock_journal = [
            {
                "id": 1,
                "date": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ref_type": "bounty_prizes",
                "amount": 1000000,
                "balance": 5000000
            }
        ]

        mock_client.get.side_effect = [mock_journal, []]

        with patch('aria_esi.commands.wallet.get_authenticated_client', return_value=(mock_client, mock_creds)):
            with patch('aria_esi.commands.wallet.ESIClient') as MockPublicClient:
                MockPublicClient.return_value = MagicMock()
                result = cmd_wallet_journal(empty_args)

        assert result.get("filter_type") == "bounty"


class TestCommandConsistency:
    """Tests for consistent command output patterns."""

    def test_all_commands_return_dict(self):
        """Verify all command functions return dicts."""
        from aria_esi.__main__ import cmd_help

        args = argparse.Namespace()

        assert isinstance(cmd_help(args), dict)
        # cmd_test_core requires mocking, tested above

    def test_error_responses_have_timestamp(self, route_args):
        """Verify error responses include query_timestamp."""
        from aria_esi.commands.navigation import cmd_route

        # Create a mock universe that doesn't recognize Dodixie
        mock_universe = MagicMock()
        mock_universe.resolve_name = MagicMock(return_value=None)

        with patch('aria_esi.commands.navigation.load_universe_graph', return_value=mock_universe):
            result = cmd_route(route_args)

        assert "query_timestamp" in result
        assert "error" in result


# =============================================================================
# Graph CLI Command Tests (STP-011)
# =============================================================================


class TestGraphCLIImports:
    """Tests that graph CLI commands can be imported."""

    def test_import_universe_commands(self):
        from aria_esi.commands import universe
        assert hasattr(universe, 'cmd_graph_build')
        assert hasattr(universe, 'cmd_graph_verify')
        assert hasattr(universe, 'cmd_graph_stats')

    def test_graph_commands_registered_in_parser(self):
        """Verify graph commands are registered in main parser."""
        from aria_esi.__main__ import build_parser

        parser = build_parser()

        # Test that graph commands parse correctly
        args = parser.parse_args(["graph-build"])
        assert args.command == "graph-build"
        assert hasattr(args, "func")

        args = parser.parse_args(["graph-verify"])
        assert args.command == "graph-verify"

        args = parser.parse_args(["graph-stats"])
        assert args.command == "graph-stats"


class TestGraphBuildCommand:
    """Tests for graph-build CLI command."""

    @pytest.fixture
    def sample_cache(self, tmp_path):
        """Create minimal universe cache for testing."""
        cache = {
            "generated": "2026-01-17T00:00:00Z",
            "regions": {
                "10000002": {"name": "The Forge"},
            },
            "constellations": {
                "20000020": {"name": "Kimotoro", "region_id": 10000002},
            },
            "systems": {
                "30000142": {
                    "name": "Jita",
                    "security": 0.95,
                    "constellation_id": 20000020,
                    "stargates": [50001],
                },
                "30000144": {
                    "name": "Perimeter",
                    "security": 0.90,
                    "constellation_id": 20000020,
                    "stargates": [50002],
                },
            },
            "stargates": {
                "50001": {"destination_system_id": 30000144},
                "50002": {"destination_system_id": 30000142},
            },
        }
        cache_path = tmp_path / "universe_cache.json"
        cache_path.write_text(json.dumps(cache))
        return cache_path

    def test_build_success(self, sample_cache, tmp_path):
        """Graph-build creates valid pickle from cache."""
        from aria_esi.commands.universe import cmd_graph_build

        output = tmp_path / "test_universe.pkl"
        args = argparse.Namespace()
        args.cache = str(sample_cache)
        args.output = str(output)
        args.force = False

        result = cmd_graph_build(args)

        assert result.get("status") == "success"
        assert result["graph"]["systems"] == 2
        assert result["graph"]["stargates"] == 1
        assert output.exists()
        assert "query_timestamp" in result

    def test_build_refuses_overwrite(self, sample_cache, tmp_path):
        """Build refuses to overwrite without --force."""
        from aria_esi.commands.universe import cmd_graph_build

        output = tmp_path / "existing.pkl"
        output.touch()  # Create existing file

        args = argparse.Namespace()
        args.cache = str(sample_cache)
        args.output = str(output)
        args.force = False

        result = cmd_graph_build(args)

        assert result.get("error") == "output_exists"
        assert "Use --force" in result.get("hint", "")

    def test_build_with_force(self, sample_cache, tmp_path):
        """Build overwrites with --force."""
        from aria_esi.commands.universe import cmd_graph_build

        output = tmp_path / "existing.pkl"
        output.touch()

        args = argparse.Namespace()
        args.cache = str(sample_cache)
        args.output = str(output)
        args.force = True

        result = cmd_graph_build(args)

        assert result.get("status") == "success"

    def test_build_missing_cache(self, tmp_path):
        """Build fails with missing cache file."""
        from aria_esi.commands.universe import cmd_graph_build

        args = argparse.Namespace()
        args.cache = str(tmp_path / "nonexistent.json")
        args.output = str(tmp_path / "output.pkl")
        args.force = False

        result = cmd_graph_build(args)

        assert result.get("error") == "cache_not_found"


class TestGraphVerifyCommand:
    """Tests for graph-verify CLI command."""

    @pytest.fixture
    def test_graph(self, tmp_path):
        """Create a test graph for verification."""
        from aria_esi.universe import build_universe_graph

        cache = {
            "generated": "2026-01-17T00:00:00Z",
            "regions": {
                "10000002": {"name": "The Forge"},
            },
            "constellations": {
                "20000020": {"name": "Kimotoro", "region_id": 10000002},
            },
            "systems": {
                "30000142": {
                    "name": "Jita",
                    "security": 0.95,
                    "constellation_id": 20000020,
                    "stargates": [50001],
                },
                "30000144": {
                    "name": "Perimeter",
                    "security": 0.90,
                    "constellation_id": 20000020,
                    "stargates": [50002],
                },
                "30002187": {
                    "name": "Amarr",
                    "security": 0.90,
                    "constellation_id": 20000020,
                    "stargates": [50003],
                },
                "30002510": {
                    "name": "Dodixie",
                    "security": 0.90,
                    "constellation_id": 20000020,
                    "stargates": [50004],
                },
                "30002659": {
                    "name": "Rens",
                    "security": 0.90,
                    "constellation_id": 20000020,
                    "stargates": [50005],
                },
                "30002053": {
                    "name": "Hek",
                    "security": 0.90,
                    "constellation_id": 20000020,
                    "stargates": [50006],
                },
            },
            "stargates": {
                "50001": {"destination_system_id": 30000144},
                "50002": {"destination_system_id": 30000142},
                "50003": {"destination_system_id": 30000142},
                "50004": {"destination_system_id": 30000142},
                "50005": {"destination_system_id": 30000142},
                "50006": {"destination_system_id": 30000142},
            },
        }
        cache_path = tmp_path / "universe_cache.json"
        cache_path.write_text(json.dumps(cache))

        graph_path = tmp_path / "universe.pkl"
        build_universe_graph(cache_path, graph_path)
        return graph_path

    def test_verify_passes_valid_graph(self, test_graph, skip_integrity_check):
        """Verify passes on valid graph."""
        from aria_esi.commands.universe import cmd_graph_verify

        args = argparse.Namespace()
        args.graph = str(test_graph)

        result = cmd_graph_verify(args)

        assert result.get("status") == "PASSED"
        assert len(result.get("checks", [])) > 0
        assert "query_timestamp" in result

    def test_verify_fails_corrupt_file(self, tmp_path):
        """Verify fails on corrupt pickle."""
        from aria_esi.commands.universe import cmd_graph_verify

        bad_graph = tmp_path / "bad.pkl"
        bad_graph.write_bytes(b"not a pickle")

        args = argparse.Namespace()
        args.graph = str(bad_graph)

        result = cmd_graph_verify(args)

        assert result.get("error") == "load_failed"

    def test_verify_missing_graph(self, tmp_path):
        """Verify fails with missing graph file."""
        from aria_esi.commands.universe import cmd_graph_verify

        args = argparse.Namespace()
        args.graph = str(tmp_path / "nonexistent.pkl")

        result = cmd_graph_verify(args)

        assert result.get("error") == "graph_not_found"


class TestGraphStatsCommand:
    """Tests for graph-stats CLI command."""

    @pytest.fixture
    def test_graph(self, tmp_path):
        """Create a test graph for stats."""
        from aria_esi.universe import build_universe_graph

        cache = {
            "generated": "2026-01-17T00:00:00Z",
            "regions": {
                "10000002": {"name": "The Forge"},
                "10000033": {"name": "The Citadel"},
            },
            "constellations": {
                "20000020": {"name": "Kimotoro", "region_id": 10000002},
                "20000404": {"name": "Saatuban", "region_id": 10000033},
            },
            "systems": {
                "30000142": {
                    "name": "Jita",
                    "security": 0.95,
                    "constellation_id": 20000020,
                    "stargates": [50001],
                },
                "30000144": {
                    "name": "Perimeter",
                    "security": 0.90,
                    "constellation_id": 20000020,
                    "stargates": [50002, 50003],
                },
                "30002769": {
                    "name": "Sivala",
                    "security": 0.35,
                    "constellation_id": 20000404,
                    "stargates": [50004],
                },
                "30002770": {
                    "name": "Ala",
                    "security": -0.2,
                    "constellation_id": 20000404,
                    "stargates": [50005],
                },
            },
            "stargates": {
                "50001": {"destination_system_id": 30000144},
                "50002": {"destination_system_id": 30000142},
                "50003": {"destination_system_id": 30002769},
                "50004": {"destination_system_id": 30000144},
                "50005": {"destination_system_id": 30002769},
            },
        }
        cache_path = tmp_path / "universe_cache.json"
        cache_path.write_text(json.dumps(cache))

        graph_path = tmp_path / "universe.pkl"
        build_universe_graph(cache_path, graph_path)
        return graph_path

    def test_stats_basic_output(self, test_graph, skip_integrity_check):
        """Stats command returns basic statistics."""
        from aria_esi.commands.universe import cmd_graph_stats

        args = argparse.Namespace()
        args.graph = str(test_graph)
        args.detailed = False

        result = cmd_graph_stats(args)

        assert "systems" in result
        assert result["systems"]["total"] == 4
        assert result["systems"]["highsec"] == 2
        assert result["systems"]["lowsec"] == 1
        assert result["systems"]["nullsec"] == 1
        assert "stargates" in result
        assert "regions" in result
        assert "query_timestamp" in result

    def test_stats_detailed_output(self, test_graph, skip_integrity_check):
        """Stats --detailed shows region breakdown."""
        from aria_esi.commands.universe import cmd_graph_stats

        args = argparse.Namespace()
        args.graph = str(test_graph)
        args.detailed = True

        result = cmd_graph_stats(args)

        assert "top_regions" in result
        assert len(result["top_regions"]) > 0
        assert "name" in result["top_regions"][0]
        assert "systems" in result["top_regions"][0]

    def test_stats_missing_graph(self, tmp_path):
        """Stats fails with missing graph file."""
        from aria_esi.commands.universe import cmd_graph_stats

        args = argparse.Namespace()
        args.graph = str(tmp_path / "nonexistent.pkl")
        args.detailed = False

        result = cmd_graph_stats(args)

        assert result.get("error") == "graph_not_found"
