"""
Tests for ESI command modules

Test coverage for authenticated ESI commands.
Current coverage levels (as of 2026-01):
- assets.py: 83% (cmd_assets, cmd_fitting, cmd_blueprints)
- skills.py: 85% (cmd_skills, cmd_skillqueue)
- contracts.py: 77% (cmd_contracts, cmd_contract_detail)
- mining.py: 75% (cmd_mining, cmd_mining_summary)
- clones.py: 71% (cmd_clones, cmd_implants, cmd_jump_clones)
- industry.py: 70% (cmd_industry_jobs)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Helper Functions
# =============================================================================


def create_mock_public_client():
    """Create mock public ESI client with type-safe method delegations.

    This creates a MagicMock that properly delegates get_dict_safe and
    get_list_safe to get_safe, matching the real ESIClient behavior.
    Tests can then set mock.get_safe.side_effect to control all lookups.
    """
    mock = MagicMock()
    mock.get_dict_safe.side_effect = lambda *a, **kw: mock.get_safe(*a, **kw) or {}
    mock.get_list_safe.side_effect = lambda *a, **kw: mock.get_safe(*a, **kw) or []
    return mock


# =============================================================================
# Helper Fixtures
# =============================================================================


@pytest.fixture
def mock_credentials():
    """Create mock credentials for testing."""
    from aria_esi.core import Credentials

    creds = MagicMock(spec=Credentials)
    creds.character_id = 12345678
    creds.access_token = "test_token"
    creds.has_scope = MagicMock(return_value=True)
    return creds


@pytest.fixture
def mock_client():
    """Create mock ESI client for testing."""
    from aria_esi.core import ESIClient

    client = MagicMock(spec=ESIClient)

    # Make type-safe getters delegate to get() for backward compatibility
    # This allows tests to set mock_client.get.return_value and have it work
    # for get_list(), get_dict(), get_list_safe(), get_dict_safe() calls too
    client.get_list.side_effect = lambda *args, **kwargs: client.get(*args, **kwargs)
    client.get_dict.side_effect = lambda *args, **kwargs: client.get(*args, **kwargs)
    client.get_list_safe.side_effect = lambda *args, **kwargs: client.get(*args, **kwargs) or []
    client.get_dict_safe.side_effect = lambda *args, **kwargs: client.get(*args, **kwargs) or {}

    return client


@pytest.fixture
def mock_public_client():
    """Create mock public ESI client for type/system lookups."""
    from aria_esi.core import ESIClient

    client = MagicMock(spec=ESIClient)
    client.get_safe = MagicMock(return_value=None)

    # Make type-safe getters delegate to get_safe for backward compatibility
    client.get_dict_safe.side_effect = lambda *args, **kwargs: client.get_safe(*args, **kwargs) or {}
    client.get_list_safe.side_effect = lambda *args, **kwargs: client.get_safe(*args, **kwargs) or []

    return client


# =============================================================================
# Clone Command Tests
# =============================================================================


class TestClonesCommand:
    """Tests for clones command."""

    def test_cmd_clones_no_credentials(self, empty_args):
        """Test clones command without credentials."""
        from aria_esi.commands.clones import cmd_clones
        from aria_esi.core import CredentialsError

        with patch("aria_esi.commands.clones.get_authenticated_client") as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_clones(empty_args)

        assert result.get("error") == "credentials_error"
        assert "query_timestamp" in result

    def test_cmd_clones_missing_scope(self, empty_args, mock_credentials, mock_client):
        """Test clones command with missing scope."""
        from aria_esi.commands.clones import cmd_clones

        mock_credentials.has_scope.return_value = False

        with patch(
            "aria_esi.commands.clones.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            result = cmd_clones(empty_args)

        assert result.get("error") == "scope_not_authorized"
        assert "esi-clones.read_clones.v1" in result.get("message", "")

    def test_cmd_clones_success(self, empty_args, mock_credentials, mock_client):
        """Test successful clones fetch."""
        from aria_esi.commands.clones import cmd_clones

        # Mock clone data response
        mock_clone_data = {
            "home_location": {"location_id": 60003760, "location_type": "station"},
            "jump_clones": [
                {
                    "jump_clone_id": 123,
                    "location_id": 60003761,
                    "location_type": "station",
                    "implants": [9899],
                    "name": "PvP Clone",
                }
            ],
            "last_clone_jump_date": (
                datetime.now(timezone.utc) - timedelta(hours=30)
            ).isoformat(),
        }

        mock_client.get.return_value = mock_clone_data

        # Mock public client for location/implant resolution
        with patch(
            "aria_esi.commands.clones.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.clones.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {
                    "name": "Jita IV - Moon 4",
                    "system_id": 30000142,
                }
                MockPublicClient.return_value = mock_public
                result = cmd_clones(empty_args)

        assert "error" not in result
        assert result.get("home_location") is not None
        assert result.get("jump_clone_count") == 1
        assert result.get("jump_available") is True  # 30 hours > 24 hour cooldown
        assert "query_timestamp" in result

    def test_cmd_clones_on_cooldown(self, empty_args, mock_credentials, mock_client):
        """Test clones command when jump is on cooldown."""
        from aria_esi.commands.clones import cmd_clones

        # Last jump was 12 hours ago (still on cooldown)
        # Use ISO format with Z suffix that parse_datetime expects
        last_jump = (datetime.now(timezone.utc) - timedelta(hours=12)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        mock_clone_data = {
            "home_location": {"location_id": 60003760, "location_type": "station"},
            "jump_clones": [],
            "last_clone_jump_date": last_jump,
        }

        mock_client.get.return_value = mock_clone_data

        with patch(
            "aria_esi.commands.clones.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.clones.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Station", "system_id": 1}
                MockPublicClient.return_value = mock_public
                result = cmd_clones(empty_args)

        assert result.get("jump_available") is False
        assert result.get("jump_cooldown_remaining") is not None

    def test_cmd_clones_esi_error(self, empty_args, mock_credentials, mock_client):
        """Test clones command with ESI error."""
        from aria_esi.commands.clones import cmd_clones
        from aria_esi.core import ESIError

        mock_client.get.side_effect = ESIError("ESI unavailable", status_code=503)

        with patch(
            "aria_esi.commands.clones.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            result = cmd_clones(empty_args)

        assert result.get("error") == "esi_error"

    def test_cmd_clones_structure_location(self, empty_args, mock_credentials, mock_client):
        """Test clones command with clone in a player structure."""
        from aria_esi.commands.clones import cmd_clones

        # Clone in a structure (not a station)
        mock_clone_data = {
            "home_location": {
                "location_id": 1035466617946,  # Player structure ID
                "location_type": "structure",
            },
            "jump_clones": [
                {
                    "jump_clone_id": 123,
                    "location_id": 1035466617946,
                    "location_type": "structure",
                    "implants": [],
                    "name": "Structure Clone",
                }
            ],
            "last_clone_jump_date": None,
        }

        mock_client.get.return_value = mock_clone_data

        with patch(
            "aria_esi.commands.clones.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.clones.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                # Structure lookups return None (not publicly accessible)
                mock_public.get_safe.return_value = None
                MockPublicClient.return_value = mock_public
                result = cmd_clones(empty_args)

        assert "error" not in result
        assert result.get("jump_clone_count") == 1
        # Structure location should be handled gracefully
        assert result.get("home_location") is not None

    def test_cmd_clones_with_implants(self, empty_args, mock_credentials, mock_client):
        """Test clones command with implants in jump clones."""
        from aria_esi.commands.clones import cmd_clones

        mock_clone_data = {
            "home_location": {"location_id": 60003760, "location_type": "station"},
            "jump_clones": [
                {
                    "jump_clone_id": 123,
                    "location_id": 60003760,
                    "location_type": "station",
                    "implants": [9899, 9900, 9901],  # 3 implants
                    "name": "Learning Clone",
                }
            ],
            "last_clone_jump_date": None,
        }

        mock_client.get.return_value = mock_clone_data

        with patch(
            "aria_esi.commands.clones.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.clones.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Jita IV - Moon 4", "system_id": 30000142}
                MockPublicClient.return_value = mock_public
                result = cmd_clones(empty_args)

        assert "error" not in result
        assert result.get("jump_clone_count") == 1
        # Check that the clone has implants recorded
        clones = result.get("jump_clones", [])
        if clones:
            assert len(clones[0].get("implants", [])) == 3 or clones[0].get("implant_count", 0) == 3


class TestImplantsCommand:
    """Tests for implants command."""

    def test_cmd_implants_no_credentials(self, empty_args):
        """Test implants command without credentials."""
        from aria_esi.commands.clones import cmd_implants
        from aria_esi.core import CredentialsError

        with patch("aria_esi.commands.clones.get_authenticated_client") as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_implants(empty_args)

        assert result.get("error") == "credentials_error"

    def test_cmd_implants_empty(self, empty_args, mock_credentials, mock_client):
        """Test implants command with no implants installed."""
        from aria_esi.commands.clones import cmd_implants

        mock_client.get.return_value = []

        with patch(
            "aria_esi.commands.clones.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.clones.ESIClient"):
                result = cmd_implants(empty_args)

        assert result.get("implant_count") == 0
        assert "No implants" in result.get("message", "")

    def test_cmd_implants_success(self, empty_args, mock_credentials, mock_client):
        """Test successful implants fetch."""
        from aria_esi.commands.clones import cmd_implants

        # Mock implant IDs
        mock_client.get.return_value = [9899, 9900, 9901]

        with patch(
            "aria_esi.commands.clones.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.clones.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                # Return implant info with slot numbers
                mock_public.get_safe.return_value = {
                    "name": "Memory Augmentation - Basic",
                    "description": "Implant",
                    "dogma_attributes": [{"attribute_id": 331, "value": 4.0}],
                }
                MockPublicClient.return_value = mock_public
                result = cmd_implants(empty_args)

        assert result.get("implant_count") == 3


class TestJumpClonesCommand:
    """Tests for jump-clones command."""

    def test_cmd_jump_clones_no_credentials(self, empty_args):
        """Test jump-clones command without credentials."""
        from aria_esi.commands.clones import cmd_jump_clones
        from aria_esi.core import CredentialsError

        with patch("aria_esi.commands.clones.get_authenticated_client") as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_jump_clones(empty_args)

        assert result.get("error") == "credentials_error"

    def test_cmd_jump_clones_success(self, empty_args, mock_credentials, mock_client):
        """Test successful jump clones fetch."""
        from aria_esi.commands.clones import cmd_jump_clones

        mock_clone_data = {
            "jump_clones": [
                {
                    "jump_clone_id": 123,
                    "location_id": 60003760,
                    "location_type": "station",
                    "implants": [9899, 9900],
                    "name": "PvP Clone",
                },
                {
                    "jump_clone_id": 124,
                    "location_id": 60003761,
                    "location_type": "station",
                    "implants": [],
                    "name": "Empty Clone",
                },
            ],
            "last_clone_jump_date": None,
        }

        mock_client.get.return_value = mock_clone_data

        with patch(
            "aria_esi.commands.clones.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.clones.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Station", "system_id": 1}
                MockPublicClient.return_value = mock_public
                result = cmd_jump_clones(empty_args)

        assert result.get("jump_clone_count") == 2
        assert result.get("jump_available") is True


# =============================================================================
# Skills Command Tests
# =============================================================================


class TestSkillsCommand:
    """Tests for skills command."""

    def test_cmd_skills_no_credentials(self, empty_args):
        """Test skills command without credentials."""
        from aria_esi.commands.skills import cmd_skills
        from aria_esi.core import CredentialsError

        with patch("aria_esi.commands.skills.get_authenticated_client") as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_skills(empty_args)

        assert result.get("error") == "credentials_error"

    def test_cmd_skills_success(self, empty_args, mock_credentials, mock_client):
        """Test successful skills fetch."""
        from aria_esi.commands.skills import cmd_skills

        empty_args.filter = None

        mock_skills_data = {
            "total_sp": 50000000,
            "unallocated_sp": 100000,
            "skills": [
                {
                    "skill_id": 3300,
                    "trained_skill_level": 5,
                    "active_skill_level": 5,
                    "skillpoints_in_skill": 256000,
                },
                {
                    "skill_id": 3301,
                    "trained_skill_level": 4,
                    "active_skill_level": 4,
                    "skillpoints_in_skill": 128000,
                },
            ],
        }

        mock_client.get.return_value = mock_skills_data

        with patch(
            "aria_esi.commands.skills.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.skills.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Spaceship Command", "group_id": 255}
                MockPublicClient.return_value = mock_public
                result = cmd_skills(empty_args)

        assert result.get("total_sp") == 50000000
        assert result.get("skill_count") == 2

    def test_cmd_skills_with_filter(self, empty_args, mock_credentials, mock_client):
        """Test skills command with name filter."""
        from aria_esi.commands.skills import cmd_skills

        empty_args.filter = "navigation"

        mock_skills_data = {
            "total_sp": 50000000,
            "unallocated_sp": 0,
            "skills": [
                {
                    "skill_id": 3300,
                    "trained_skill_level": 5,
                    "active_skill_level": 5,
                    "skillpoints_in_skill": 256000,
                }
            ],
        }

        mock_client.get.return_value = mock_skills_data

        with patch(
            "aria_esi.commands.skills.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.skills.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                # Return "Navigation" skill so filter matches
                mock_public.get_safe.return_value = {"name": "Navigation", "group_id": 255}
                MockPublicClient.return_value = mock_public
                result = cmd_skills(empty_args)

        assert result.get("filter_applied") == "navigation"


class TestSkillqueueCommand:
    """Tests for skillqueue command."""

    def test_cmd_skillqueue_no_credentials(self, empty_args):
        """Test skillqueue command without credentials."""
        from aria_esi.commands.skills import cmd_skillqueue
        from aria_esi.core import CredentialsError

        with patch("aria_esi.commands.skills.get_authenticated_client") as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_skillqueue(empty_args)

        assert result.get("error") == "credentials_error"

    def test_cmd_skillqueue_empty(self, empty_args, mock_credentials, mock_client):
        """Test skillqueue command with empty queue."""
        from aria_esi.commands.skills import cmd_skillqueue

        mock_client.get.return_value = []

        with patch(
            "aria_esi.commands.skills.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            result = cmd_skillqueue(empty_args)

        assert result.get("queue_status") == "empty"
        assert "empty" in result.get("message", "").lower()

    def test_cmd_skillqueue_active(self, empty_args, mock_credentials, mock_client):
        """Test skillqueue command with active training."""
        from aria_esi.commands.skills import cmd_skillqueue

        now = datetime.now(timezone.utc)
        finish_time = now + timedelta(hours=5)

        # Use ISO format with Z suffix that parse_datetime expects
        mock_queue = [
            {
                "skill_id": 3300,
                "finished_level": 5,
                "queue_position": 0,
                "start_date": (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "finish_date": finish_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            {
                "skill_id": 3301,
                "finished_level": 4,
                "queue_position": 1,
                "start_date": finish_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "finish_date": (finish_time + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        ]

        mock_client.get.return_value = mock_queue

        with patch(
            "aria_esi.commands.skills.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.skills.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Test Skill"}
                MockPublicClient.return_value = mock_public
                result = cmd_skillqueue(empty_args)

        assert result.get("queue_status") == "active"
        assert result.get("queue_length") == 2
        assert result.get("currently_training") is not None


# =============================================================================
# Industry Command Tests
# =============================================================================


class TestIndustryJobsCommand:
    """Tests for industry-jobs command."""

    def test_cmd_industry_jobs_no_credentials(self, empty_args):
        """Test industry-jobs command without credentials."""
        from aria_esi.commands.industry import cmd_industry_jobs
        from aria_esi.core import CredentialsError

        with patch("aria_esi.commands.industry.get_authenticated_client") as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_industry_jobs(empty_args)

        assert result.get("error") == "credentials_error"

    def test_cmd_industry_jobs_empty(self, empty_args, mock_credentials, mock_client):
        """Test industry-jobs command with no jobs."""
        from aria_esi.commands.industry import cmd_industry_jobs

        empty_args.filter_mode = None
        mock_client.get.return_value = []

        with patch(
            "aria_esi.commands.industry.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            result = cmd_industry_jobs(empty_args)

        assert result.get("summary", {}).get("active_jobs") == 0
        assert "No industry jobs" in result.get("message", "")

    def test_cmd_industry_jobs_active(self, empty_args, mock_credentials, mock_client):
        """Test industry-jobs command with active jobs."""
        from aria_esi.commands.industry import cmd_industry_jobs

        empty_args.filter_mode = None
        now = datetime.now(timezone.utc)

        mock_jobs = [
            {
                "job_id": 123,
                "activity_id": 1,  # Manufacturing
                "blueprint_type_id": 687,
                "product_type_id": 587,
                "runs": 10,
                "status": "active",
                "facility_id": 60003760,
                "start_date": (now - timedelta(hours=1)).isoformat(),
                "end_date": (now + timedelta(hours=5)).isoformat(),
                "cost": 100000,
            },
            {
                "job_id": 124,
                "activity_id": 4,  # ME Research
                "blueprint_type_id": 687,
                "runs": 1,
                "status": "active",
                "facility_id": 60003760,
                "start_date": now.isoformat(),
                "end_date": (now + timedelta(days=1)).isoformat(),
                "cost": 50000,
            },
        ]

        mock_client.get.return_value = mock_jobs

        with patch(
            "aria_esi.commands.industry.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.industry.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Test Blueprint"}
                MockPublicClient.return_value = mock_public
                result = cmd_industry_jobs(empty_args)

        assert result.get("summary", {}).get("active_jobs") == 2

    def test_cmd_industry_jobs_completed(self, empty_args, mock_credentials, mock_client):
        """Test industry-jobs with completed job (ready for delivery)."""
        from aria_esi.commands.industry import cmd_industry_jobs

        empty_args.filter_mode = None
        now = datetime.now(timezone.utc)

        # Job ended 1 hour ago but not delivered - use ISO format with Z suffix
        mock_jobs = [
            {
                "job_id": 125,
                "activity_id": 1,
                "blueprint_type_id": 687,
                "product_type_id": 587,
                "runs": 5,
                "status": "active",  # Still marked active
                "facility_id": 60003760,
                "start_date": (now - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_date": (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),  # Ended
                "cost": 10000,
            }
        ]

        mock_client.get.return_value = mock_jobs

        with patch(
            "aria_esi.commands.industry.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.industry.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Blueprint"}
                MockPublicClient.return_value = mock_public
                result = cmd_industry_jobs(empty_args)

        # Job should be marked as "ready" since end_date is in the past
        assert result.get("summary", {}).get("completed_awaiting_delivery") == 1

    def test_cmd_industry_jobs_active_filter(self, empty_args, mock_credentials, mock_client):
        """Test industry-jobs command with active filter."""
        from aria_esi.commands.industry import cmd_industry_jobs

        empty_args.filter_mode = "active"
        now = datetime.now(timezone.utc)

        mock_jobs = [
            {
                "job_id": 123,
                "activity_id": 1,  # Manufacturing
                "blueprint_type_id": 687,
                "product_type_id": 587,
                "runs": 10,
                "status": "active",
                "facility_id": 60003760,
                "start_date": (now - timedelta(hours=1)).isoformat(),
                "end_date": (now + timedelta(hours=5)).isoformat(),
                "cost": 100000,
            },
            {
                "job_id": 124,
                "activity_id": 1,
                "blueprint_type_id": 687,
                "product_type_id": 587,
                "runs": 5,
                "status": "delivered",  # Should be filtered out
                "facility_id": 60003760,
                "start_date": (now - timedelta(days=2)).isoformat(),
                "end_date": (now - timedelta(days=1)).isoformat(),
                "cost": 50000,
            },
        ]

        mock_client.get.return_value = mock_jobs

        with patch(
            "aria_esi.commands.industry.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.industry.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Test Blueprint"}
                MockPublicClient.return_value = mock_public
                result = cmd_industry_jobs(empty_args)

        # Only active jobs should be in results
        jobs = result.get("jobs", [])
        assert len(jobs) == 1
        assert jobs[0]["status"] == "active"

    def test_cmd_industry_jobs_history_filter(self, empty_args, mock_credentials, mock_client):
        """Test industry-jobs command with history filter."""
        from aria_esi.commands.industry import cmd_industry_jobs

        empty_args.filter_mode = "history"
        now = datetime.now(timezone.utc)

        mock_jobs = [
            {
                "job_id": 123,
                "activity_id": 1,
                "blueprint_type_id": 687,
                "product_type_id": 587,
                "runs": 10,
                "status": "active",
                "facility_id": 60003760,
                "start_date": (now - timedelta(hours=1)).isoformat(),
                "end_date": (now + timedelta(hours=5)).isoformat(),
                "cost": 100000,
            },
            {
                "job_id": 124,
                "activity_id": 1,
                "blueprint_type_id": 687,
                "product_type_id": 587,
                "runs": 5,
                "status": "delivered",
                "facility_id": 60003760,
                "start_date": (now - timedelta(days=2)).isoformat(),
                "end_date": (now - timedelta(days=1)).isoformat(),
                "cost": 50000,
            },
        ]

        mock_client.get.return_value = mock_jobs

        with patch(
            "aria_esi.commands.industry.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.industry.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Test Blueprint"}
                MockPublicClient.return_value = mock_public
                result = cmd_industry_jobs(empty_args)

        # Both active and delivered jobs should be in results
        jobs = result.get("jobs", [])
        assert len(jobs) == 2
        statuses = {j["status"] for j in jobs}
        assert "active" in statuses
        assert "delivered" in statuses


# =============================================================================
# Mining Command Tests
# =============================================================================


class TestMiningCommand:
    """Tests for mining command."""

    def test_cmd_mining_no_credentials(self, empty_args):
        """Test mining command without credentials."""
        from aria_esi.commands.mining import cmd_mining
        from aria_esi.core import CredentialsError

        empty_args.days = 30
        empty_args.system = None
        empty_args.ore = None

        with patch("aria_esi.commands.mining.get_authenticated_client") as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_mining(empty_args)

        assert result.get("error") == "credentials_error"

    def test_cmd_mining_missing_scope(self, empty_args, mock_credentials, mock_client):
        """Test mining command with missing scope."""
        from aria_esi.commands.mining import cmd_mining

        empty_args.days = 30
        empty_args.system = None
        empty_args.ore = None
        mock_credentials.has_scope.return_value = False

        with patch(
            "aria_esi.commands.mining.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            result = cmd_mining(empty_args)

        assert result.get("error") == "scope_not_authorized"

    def test_cmd_mining_empty(self, empty_args, mock_credentials, mock_client):
        """Test mining command with no mining activity."""
        from aria_esi.commands.mining import cmd_mining

        empty_args.days = 30
        empty_args.system = None
        empty_args.ore = None
        mock_client.get.return_value = []

        with patch(
            "aria_esi.commands.mining.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            result = cmd_mining(empty_args)

        assert result.get("summary", {}).get("total_entries") == 0
        assert "No mining activity" in result.get("message", "")

    def test_cmd_mining_success(self, empty_args, mock_credentials, mock_client):
        """Test successful mining ledger fetch."""
        from aria_esi.commands.mining import cmd_mining

        empty_args.days = 30
        empty_args.system = None
        empty_args.ore = None

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        mock_entries = [
            {
                "date": today,
                "type_id": 1230,  # Veldspar
                "solar_system_id": 30000142,
                "quantity": 10000,
            },
            {
                "date": today,
                "type_id": 1228,  # Scordite
                "solar_system_id": 30000142,
                "quantity": 5000,
            },
        ]

        # First call returns entries, second call returns empty (pagination)
        mock_client.get.side_effect = [mock_entries, []]

        with patch(
            "aria_esi.commands.mining.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.mining.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()

                def get_safe_handler(url):
                    if "/types/1230" in url:
                        return {"name": "Veldspar"}
                    elif "/types/1228" in url:
                        return {"name": "Scordite"}
                    elif "/systems/30000142" in url:
                        return {"name": "Jita", "security_status": 0.95}
                    return {"name": "Unknown"}

                mock_public.get_safe.side_effect = get_safe_handler
                MockPublicClient.return_value = mock_public
                result = cmd_mining(empty_args)

        assert result.get("summary", {}).get("total_quantity") == 15000
        assert result.get("summary", {}).get("unique_ores") == 2

    def test_cmd_mining_with_system_filter(self, empty_args, mock_credentials, mock_client):
        """Test mining command with system filter."""
        from aria_esi.commands.mining import cmd_mining

        empty_args.days = 30
        empty_args.system = "Jita"
        empty_args.ore = None

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        mock_entries = [
            {
                "date": today,
                "type_id": 1230,
                "solar_system_id": 30000142,  # Jita
                "quantity": 10000,
            },
            {
                "date": today,
                "type_id": 1230,
                "solar_system_id": 30002187,  # Amarr (should be filtered out)
                "quantity": 5000,
            },
        ]

        # First call returns entries, second call returns empty (pagination)
        mock_client.get.side_effect = [mock_entries, []]

        with patch(
            "aria_esi.commands.mining.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.mining.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()

                def get_safe_side_effect(url):
                    if "/systems/30000142" in url:
                        return {"name": "Jita", "security_status": 0.95}
                    elif "/systems/30002187" in url:
                        return {"name": "Amarr", "security_status": 0.9}
                    elif "/types/" in url:
                        return {"name": "Veldspar"}
                    return {"name": "Unknown"}

                mock_public.get_safe.side_effect = get_safe_side_effect
                MockPublicClient.return_value = mock_public
                result = cmd_mining(empty_args)

        # Only Jita entries should be included
        assert result.get("summary", {}).get("total_quantity") == 10000

    def test_cmd_mining_with_ore_filter(self, empty_args, mock_credentials, mock_client):
        """Test mining command with ore type filter."""
        from aria_esi.commands.mining import cmd_mining

        empty_args.days = 30
        empty_args.system = None
        empty_args.ore = "Veldspar"

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        mock_entries = [
            {
                "date": today,
                "type_id": 1230,  # Veldspar
                "solar_system_id": 30000142,
                "quantity": 10000,
            },
            {
                "date": today,
                "type_id": 1228,  # Scordite (should be filtered out)
                "solar_system_id": 30000142,
                "quantity": 5000,
            },
        ]

        # First call returns entries, second call returns empty (pagination)
        mock_client.get.side_effect = [mock_entries, []]

        with patch(
            "aria_esi.commands.mining.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.mining.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()

                def get_safe_side_effect(url):
                    if "/types/1230" in url:
                        return {"name": "Veldspar"}
                    elif "/types/1228" in url:
                        return {"name": "Scordite"}
                    elif "/systems/" in url:
                        return {"name": "Jita", "security_status": 0.95}
                    return {"name": "Unknown"}

                mock_public.get_safe.side_effect = get_safe_side_effect
                MockPublicClient.return_value = mock_public
                result = cmd_mining(empty_args)

        # Only Veldspar entries should be included
        assert result.get("summary", {}).get("total_quantity") == 10000
        assert result.get("summary", {}).get("unique_ores") == 1

    def test_cmd_mining_pagination(self, empty_args, mock_credentials, mock_client):
        """Test mining command handles pagination correctly."""
        from aria_esi.commands.mining import cmd_mining

        empty_args.days = 30
        empty_args.system = None
        empty_args.ore = None

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Simulate paginated responses
        page1_entries = [
            {"date": today, "type_id": 1230, "solar_system_id": 30000142, "quantity": 5000}
        ]
        page2_entries = [
            {"date": today, "type_id": 1230, "solar_system_id": 30000142, "quantity": 3000}
        ]
        page3_empty = []

        mock_client.get.side_effect = [page1_entries, page2_entries, page3_empty]

        with patch(
            "aria_esi.commands.mining.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.mining.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Veldspar", "security_status": 0.95}
                MockPublicClient.return_value = mock_public
                result = cmd_mining(empty_args)

        # Should have combined entries from both pages
        assert result.get("summary", {}).get("total_quantity") == 8000


class TestMiningSummaryCommand:
    """Tests for mining-summary command."""

    def test_cmd_mining_summary_no_credentials(self, empty_args):
        """Test mining-summary command without credentials."""
        from aria_esi.commands.mining import cmd_mining_summary
        from aria_esi.core import CredentialsError

        empty_args.days = 30

        with patch("aria_esi.commands.mining.get_authenticated_client") as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_mining_summary(empty_args)

        assert result.get("error") == "credentials_error"

    def test_cmd_mining_summary_success(self, empty_args, mock_credentials, mock_client):
        """Test successful mining summary."""
        from aria_esi.commands.mining import cmd_mining_summary

        empty_args.days = 30

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        mock_entries = [
            {"date": today, "type_id": 1230, "solar_system_id": 30000142, "quantity": 10000},
            {"date": today, "type_id": 1230, "solar_system_id": 30000142, "quantity": 5000},
            {"date": today, "type_id": 1228, "solar_system_id": 30002187, "quantity": 8000},
        ]

        # First call returns entries, second call returns empty (pagination)
        mock_client.get.side_effect = [mock_entries, []]

        with patch(
            "aria_esi.commands.mining.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.mining.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()

                def get_safe_handler(url):
                    if "/types/1230" in url:
                        return {"name": "Veldspar"}
                    elif "/types/1228" in url:
                        return {"name": "Scordite"}
                    elif "/systems/30000142" in url:
                        return {"name": "Jita"}
                    elif "/systems/30002187" in url:
                        return {"name": "Amarr"}
                    return {"name": "Unknown"}

                mock_public.get_safe.side_effect = get_safe_handler
                MockPublicClient.return_value = mock_public
                result = cmd_mining_summary(empty_args)

        assert result.get("summary", {}).get("total_quantity") == 23000
        assert len(result.get("by_ore", [])) >= 1


# =============================================================================
# Contracts Command Tests
# =============================================================================


class TestContractsCommand:
    """Tests for contracts command."""

    def test_cmd_contracts_no_credentials(self, empty_args):
        """Test contracts command without credentials."""
        from aria_esi.commands.contracts import cmd_contracts
        from aria_esi.core import CredentialsError

        empty_args.issued = False
        empty_args.received = False
        empty_args.type = None
        empty_args.active = False
        empty_args.completed = False
        empty_args.limit = 20

        with patch("aria_esi.commands.contracts.get_authenticated_client") as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_contracts(empty_args)

        assert result.get("error") == "credentials_error"

    def test_cmd_contracts_missing_scope(self, empty_args, mock_credentials, mock_client):
        """Test contracts command with missing scope."""
        from aria_esi.commands.contracts import cmd_contracts

        empty_args.issued = False
        empty_args.received = False
        empty_args.type = None
        empty_args.active = False
        empty_args.completed = False
        empty_args.limit = 20
        mock_credentials.has_scope.return_value = False

        with patch(
            "aria_esi.commands.contracts.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            result = cmd_contracts(empty_args)

        assert result.get("error") == "scope_not_authorized"

    def test_cmd_contracts_empty(self, empty_args, mock_credentials, mock_client):
        """Test contracts command with no contracts."""
        from aria_esi.commands.contracts import cmd_contracts

        empty_args.issued = False
        empty_args.received = False
        empty_args.type = None
        empty_args.active = False
        empty_args.completed = False
        empty_args.limit = 20
        mock_client.get.return_value = []

        with patch(
            "aria_esi.commands.contracts.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            result = cmd_contracts(empty_args)

        assert result.get("summary", {}).get("total_contracts") == 0
        assert "No contracts" in result.get("message", "")

    def test_cmd_contracts_item_exchange(self, empty_args, mock_credentials, mock_client):
        """Test contracts command with item exchange contract."""
        from aria_esi.commands.contracts import cmd_contracts

        empty_args.issued = False
        empty_args.received = False
        empty_args.type = None
        empty_args.active = False
        empty_args.completed = False
        empty_args.limit = 20

        now = datetime.now(timezone.utc)
        mock_contracts = [
            {
                "contract_id": 123,
                "type": "item_exchange",
                "status": "outstanding",
                "issuer_id": 12345678,  # Same as character
                "acceptor_id": None,
                "assignee_id": 0,
                "availability": "public",
                "title": "Selling stuff",
                "price": 1000000,
                "date_issued": (now - timedelta(days=1)).isoformat(),
                "date_expired": (now + timedelta(days=6)).isoformat(),
            }
        ]

        mock_client.get.return_value = mock_contracts

        with patch(
            "aria_esi.commands.contracts.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.contracts.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Test Pilot"}
                MockPublicClient.return_value = mock_public
                result = cmd_contracts(empty_args)

        assert result.get("summary", {}).get("total_contracts") == 1
        assert result.get("summary", {}).get("outstanding") == 1

    def test_cmd_contracts_courier(self, empty_args, mock_credentials, mock_client):
        """Test contracts command with courier contract."""
        from aria_esi.commands.contracts import cmd_contracts

        empty_args.issued = False
        empty_args.received = False
        empty_args.type = "courier"
        empty_args.active = False
        empty_args.completed = False
        empty_args.limit = 20

        now = datetime.now(timezone.utc)
        mock_contracts = [
            {
                "contract_id": 124,
                "type": "courier",
                "status": "outstanding",
                "issuer_id": 12345678,
                "acceptor_id": None,
                "assignee_id": 0,
                "availability": "public",
                "reward": 5000000,
                "collateral": 100000000,
                "volume": 10000,
                "days_to_complete": 3,
                "start_location_id": 60003760,
                "end_location_id": 60003761,
                "date_issued": (now - timedelta(days=1)).isoformat(),
                "date_expired": (now + timedelta(days=6)).isoformat(),
            }
        ]

        mock_client.get.return_value = mock_contracts

        with patch(
            "aria_esi.commands.contracts.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.contracts.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Station"}
                MockPublicClient.return_value = mock_public
                result = cmd_contracts(empty_args)

        assert result.get("summary", {}).get("by_type", {}).get("courier") == 1


class TestContractDetailCommand:
    """Tests for contract detail command."""

    def test_cmd_contract_detail_missing_id(self, empty_args):
        """Test contract detail without contract ID."""
        from aria_esi.commands.contracts import cmd_contract_detail

        empty_args.contract_id = None

        result = cmd_contract_detail(empty_args)

        assert result.get("error") == "missing_argument"

    def test_cmd_contract_detail_not_found(self, empty_args, mock_credentials, mock_client):
        """Test contract detail for non-existent contract."""
        from aria_esi.commands.contracts import cmd_contract_detail

        empty_args.contract_id = 999

        mock_client.get.return_value = []  # No contracts

        with patch(
            "aria_esi.commands.contracts.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            result = cmd_contract_detail(empty_args)

        assert result.get("error") == "contract_not_found"

    def test_cmd_contract_detail_item_exchange(
        self, empty_args, mock_credentials, mock_client, mock_contract_items_response
    ):
        """Test contract detail for item exchange with items list."""
        from aria_esi.commands.contracts import cmd_contract_detail

        empty_args.contract_id = 123
        now = datetime.now(timezone.utc)

        mock_contracts = [
            {
                "contract_id": 123,
                "type": "item_exchange",
                "status": "outstanding",
                "issuer_id": 12345678,
                "acceptor_id": None,
                "assignee_id": 0,
                "availability": "public",
                "title": "Selling minerals",
                "price": 5000000,
                "date_issued": (now - timedelta(days=1)).isoformat(),
                "date_expired": (now + timedelta(days=6)).isoformat(),
            }
        ]

        # First call returns contracts, second call returns items
        mock_client.get.side_effect = [mock_contracts, mock_contract_items_response]

        with patch(
            "aria_esi.commands.contracts.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.contracts.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()

                def get_safe_handler(url):
                    if "/characters/12345678" in url:
                        return {"name": "Test Pilot"}
                    elif "/types/34" in url:
                        return {"name": "Tritanium"}
                    elif "/types/35" in url:
                        return {"name": "Pyerite"}
                    return {"name": "Unknown"}

                mock_public.get_safe.side_effect = get_safe_handler
                MockPublicClient.return_value = mock_public
                result = cmd_contract_detail(empty_args)

        assert result.get("contract_id") == 123
        assert result.get("type") == "item_exchange"
        assert result.get("items_count") == 2
        assert result.get("price") == 5000000

    def test_cmd_contract_detail_courier(self, empty_args, mock_credentials, mock_client):
        """Test contract detail for courier contract with pickup/destination."""
        from aria_esi.commands.contracts import cmd_contract_detail

        empty_args.contract_id = 124
        now = datetime.now(timezone.utc)

        mock_contracts = [
            {
                "contract_id": 124,
                "type": "courier",
                "status": "outstanding",
                "issuer_id": 12345678,
                "acceptor_id": None,
                "assignee_id": 0,
                "availability": "public",
                "reward": 5000000,
                "collateral": 100000000,
                "volume": 10000,
                "days_to_complete": 3,
                "start_location_id": 60003760,
                "end_location_id": 60003761,
                "date_issued": (now - timedelta(days=1)).isoformat(),
                "date_expired": (now + timedelta(days=6)).isoformat(),
            }
        ]

        # First call returns contracts, second returns empty items
        mock_client.get.side_effect = [mock_contracts, []]

        with patch(
            "aria_esi.commands.contracts.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.contracts.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()

                def get_safe_handler(url):
                    if "/characters/" in url:
                        return {"name": "Test Pilot"}
                    elif "/stations/60003760" in url:
                        return {"name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant"}
                    elif "/stations/60003761" in url:
                        return {"name": "Amarr VIII - Oris - Emperor Family Academy"}
                    return {"name": "Unknown"}

                mock_public.get_safe.side_effect = get_safe_handler
                MockPublicClient.return_value = mock_public
                result = cmd_contract_detail(empty_args)

        assert result.get("contract_id") == 124
        assert result.get("type") == "courier"
        assert result.get("reward") == 5000000
        assert result.get("collateral") == 100000000
        assert result.get("volume") == 10000
        assert "Jita" in result.get("start_location", "")
        assert "Amarr" in result.get("end_location", "")

    def test_cmd_contract_detail_auction_with_bids(
        self, empty_args, mock_credentials, mock_client, mock_contract_bids_response
    ):
        """Test contract detail for auction type with bid history."""
        from aria_esi.commands.contracts import cmd_contract_detail

        empty_args.contract_id = 125
        now = datetime.now(timezone.utc)

        mock_contracts = [
            {
                "contract_id": 125,
                "type": "auction",
                "status": "outstanding",
                "issuer_id": 12345678,
                "acceptor_id": None,
                "assignee_id": 0,
                "availability": "public",
                "price": 1000000,  # Starting price
                "buyout": 10000000,
                "date_issued": (now - timedelta(days=1)).isoformat(),
                "date_expired": (now + timedelta(days=6)).isoformat(),
            }
        ]

        # First call returns contracts, second returns items, third returns bids
        mock_client.get.side_effect = [mock_contracts, [], mock_contract_bids_response]

        with patch(
            "aria_esi.commands.contracts.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.contracts.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()

                def get_safe_handler(url):
                    if "/characters/12345678" in url:
                        return {"name": "Test Pilot"}
                    elif "/characters/98765432" in url:
                        return {"name": "Bidder One"}
                    elif "/characters/87654321" in url:
                        return {"name": "Bidder Two"}
                    return {"name": "Unknown"}

                mock_public.get_safe.side_effect = get_safe_handler
                MockPublicClient.return_value = mock_public
                result = cmd_contract_detail(empty_args)

        assert result.get("contract_id") == 125
        assert result.get("type") == "auction"
        assert result.get("buyout") == 10000000
        assert result.get("bid_count") == 2
        # Bids should be sorted by amount descending
        bids = result.get("bids", [])
        assert len(bids) == 2
        assert bids[0]["amount"] == 5000000
        assert bids[1]["amount"] == 3000000

    def test_cmd_contracts_active_filter(self, empty_args, mock_credentials, mock_client):
        """Test contracts command with active filter."""
        from aria_esi.commands.contracts import cmd_contracts

        empty_args.issued = False
        empty_args.received = False
        empty_args.type = None
        empty_args.active = True
        empty_args.completed = False
        empty_args.limit = 20

        now = datetime.now(timezone.utc)
        mock_contracts = [
            {
                "contract_id": 123,
                "type": "item_exchange",
                "status": "outstanding",  # Active
                "issuer_id": 12345678,
                "acceptor_id": None,
                "assignee_id": 0,
                "date_issued": (now - timedelta(days=1)).isoformat(),
                "date_expired": (now + timedelta(days=6)).isoformat(),
            },
            {
                "contract_id": 124,
                "type": "item_exchange",
                "status": "finished",  # Not active
                "issuer_id": 12345678,
                "acceptor_id": 99999999,
                "assignee_id": 0,
                "date_issued": (now - timedelta(days=5)).isoformat(),
                "date_expired": (now - timedelta(days=1)).isoformat(),
            },
        ]

        mock_client.get.return_value = mock_contracts

        with patch(
            "aria_esi.commands.contracts.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.contracts.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Test Pilot"}
                MockPublicClient.return_value = mock_public
                result = cmd_contracts(empty_args)

        # Only active contract should be in results
        contracts = result.get("contracts", [])
        assert len(contracts) == 1
        assert contracts[0]["status"] == "outstanding"

    def test_cmd_contracts_completed_filter(self, empty_args, mock_credentials, mock_client):
        """Test contracts command with completed filter."""
        from aria_esi.commands.contracts import cmd_contracts

        empty_args.issued = False
        empty_args.received = False
        empty_args.type = None
        empty_args.active = False
        empty_args.completed = True
        empty_args.limit = 20

        now = datetime.now(timezone.utc)
        mock_contracts = [
            {
                "contract_id": 123,
                "type": "item_exchange",
                "status": "outstanding",  # Active
                "issuer_id": 12345678,
                "acceptor_id": None,
                "assignee_id": 0,
                "date_issued": (now - timedelta(days=1)).isoformat(),
                "date_expired": (now + timedelta(days=6)).isoformat(),
            },
            {
                "contract_id": 124,
                "type": "item_exchange",
                "status": "finished",  # Completed
                "issuer_id": 12345678,
                "acceptor_id": 99999999,
                "assignee_id": 0,
                "date_issued": (now - timedelta(days=5)).isoformat(),
                "date_expired": (now - timedelta(days=1)).isoformat(),
            },
        ]

        mock_client.get.return_value = mock_contracts

        with patch(
            "aria_esi.commands.contracts.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.contracts.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Test Pilot"}
                MockPublicClient.return_value = mock_public
                result = cmd_contracts(empty_args)

        # Only completed contract should be in results
        contracts = result.get("contracts", [])
        assert len(contracts) == 1
        assert contracts[0]["status"] == "finished"


# =============================================================================
# Assets Command Tests
# =============================================================================


class TestAssetsCommand:
    """Tests for assets command."""

    def test_cmd_assets_no_credentials(self, empty_args):
        """Test assets command without credentials."""
        from aria_esi.commands.assets import cmd_assets
        from aria_esi.core import CredentialsError

        empty_args.filter_type = None
        empty_args.type_filter = None
        empty_args.location_filter = None

        with patch("aria_esi.commands.assets.get_authenticated_client") as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_assets(empty_args)

        assert result.get("error") == "credentials_error"

    def test_cmd_assets_empty(self, empty_args, mock_credentials, mock_client):
        """Test assets command with no assets."""
        from aria_esi.commands.assets import cmd_assets

        empty_args.filter_type = None
        empty_args.type_filter = None
        empty_args.location_filter = None
        mock_client.get.return_value = []

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            result = cmd_assets(empty_args)

        assert result.get("total_assets") == 0
        assert "No assets" in result.get("message", "")

    def test_cmd_assets_success(self, empty_args, mock_credentials, mock_client):
        """Test successful assets fetch."""
        from aria_esi.commands.assets import cmd_assets

        empty_args.filter_type = None
        empty_args.type_filter = None
        empty_args.location_filter = None

        mock_assets = [
            {
                "item_id": 1001,
                "type_id": 587,  # Rifter
                "location_id": 60003760,
                "location_type": "station",
                "location_flag": "Hangar",
                "quantity": 1,
                "is_singleton": True,
            },
            {
                "item_id": 1002,
                "type_id": 34,  # Tritanium
                "location_id": 60003760,
                "location_type": "station",
                "location_flag": "Hangar",
                "quantity": 100000,
                "is_singleton": False,
            },
        ]

        mock_client.get.return_value = mock_assets

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.side_effect = [
                    {"name": "Rifter", "group_id": 25},  # Frigate
                    {"name": "Tritanium", "group_id": 18},  # Mineral
                    {"name": "Jita IV - Moon 4"},  # Station
                ]
                MockPublicClient.return_value = mock_public
                result = cmd_assets(empty_args)

        assert result.get("total_assets") == 2
        assert result.get("filtered_count") == 2

    def test_cmd_assets_ships_filter(self, empty_args, mock_credentials, mock_client):
        """Test assets command with ships filter."""
        from aria_esi.commands.assets import cmd_assets

        empty_args.filter_type = "ships"
        empty_args.type_filter = None
        empty_args.location_filter = None

        mock_assets = [
            {
                "item_id": 1001,
                "type_id": 587,  # Rifter
                "location_id": 60003760,
                "location_type": "station",
                "location_flag": "Hangar",
                "quantity": 1,
                "is_singleton": True,  # Assembled
            },
            {
                "item_id": 1002,
                "type_id": 587,  # Rifter
                "location_id": 60003760,
                "location_type": "station",
                "location_flag": "Hangar",
                "quantity": 1,
                "is_singleton": False,  # Packaged - should be excluded
            },
            {
                "item_id": 1003,
                "type_id": 34,  # Tritanium - not a ship
                "location_id": 60003760,
                "location_type": "station",
                "location_flag": "Hangar",
                "quantity": 100000,
                "is_singleton": False,
            },
        ]

        mock_client.get.return_value = mock_assets

        # Mock SHIP_GROUP_IDS to include 25 (Frigate)
        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.SHIP_GROUP_IDS", {25}):
                with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                    mock_public = create_mock_public_client()
                    mock_public.get_safe.side_effect = [
                        {"name": "Rifter", "group_id": 25},
                        {"name": "Rifter", "group_id": 25},
                        {"name": "Tritanium", "group_id": 18},
                        {"name": "Jita IV"},
                    ]
                    MockPublicClient.return_value = mock_public
                    result = cmd_assets(empty_args)

        # Only the assembled ship should be returned
        assert result.get("ship_count") == 1

    def test_cmd_assets_type_filter(self, empty_args, mock_credentials, mock_client):
        """Test assets command with type name filter."""
        from aria_esi.commands.assets import cmd_assets

        empty_args.filter_type = None
        empty_args.type_filter = "Rifter"
        empty_args.location_filter = None

        mock_assets = [
            {
                "item_id": 1001,
                "type_id": 587,
                "location_id": 60003760,
                "location_type": "station",
                "location_flag": "Hangar",
                "quantity": 1,
                "is_singleton": True,
            },
            {
                "item_id": 1002,
                "type_id": 34,
                "location_id": 60003760,
                "location_type": "station",
                "location_flag": "Hangar",
                "quantity": 100000,
                "is_singleton": False,
            },
        ]

        mock_client.get.return_value = mock_assets

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.side_effect = [
                    {"name": "Rifter", "group_id": 25},
                    {"name": "Tritanium", "group_id": 18},
                    {"name": "Jita IV"},
                ]
                MockPublicClient.return_value = mock_public
                result = cmd_assets(empty_args)

        # Only Rifter should match the filter
        assert result.get("filtered_count") == 1
        assert result.get("filter", {}).get("type") == "type"
        assert result.get("filter", {}).get("value") == "Rifter"

    def test_cmd_assets_location_filter(self, empty_args, mock_credentials, mock_client):
        """Test assets command with location filter."""
        from aria_esi.commands.assets import cmd_assets

        empty_args.filter_type = None
        empty_args.type_filter = None
        empty_args.location_filter = "Jita"

        mock_assets = [
            {
                "item_id": 1001,
                "type_id": 587,
                "location_id": 60003760,
                "location_type": "station",
                "location_flag": "Hangar",
                "quantity": 1,
                "is_singleton": True,
            },
            {
                "item_id": 1002,
                "type_id": 34,
                "location_id": 60003761,  # Different station
                "location_type": "station",
                "location_flag": "Hangar",
                "quantity": 100000,
                "is_singleton": False,
            },
        ]

        mock_client.get.return_value = mock_assets

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()

                def get_safe_side_effect(url):
                    if "/types/587" in url:
                        return {"name": "Rifter", "group_id": 25}
                    elif "/types/34" in url:
                        return {"name": "Tritanium", "group_id": 18}
                    elif "/stations/60003760" in url:
                        return {"name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant"}
                    elif "/stations/60003761" in url:
                        return {"name": "Amarr VIII - Oris - Emperor Family Academy"}
                    return {"name": "Unknown"}

                mock_public.get_safe.side_effect = get_safe_side_effect
                MockPublicClient.return_value = mock_public
                result = cmd_assets(empty_args)

        # Only Jita station assets should match
        assert result.get("filtered_count") == 1
        assert result.get("filter", {}).get("type") == "location"
        assert result.get("filter", {}).get("value") == "Jita"

    def test_cmd_assets_truncation(self, empty_args, mock_credentials, mock_client):
        """Test assets command truncates results beyond 100 items."""
        from aria_esi.commands.assets import cmd_assets

        empty_args.filter_type = None
        empty_args.type_filter = None
        empty_args.location_filter = None

        # Create 150 mock assets
        mock_assets = [
            {
                "item_id": 1000 + i,
                "type_id": 34,  # Tritanium
                "location_id": 60003760,
                "location_type": "station",
                "location_flag": "Hangar",
                "quantity": 100,
                "is_singleton": False,
            }
            for i in range(150)
        ]

        mock_client.get.return_value = mock_assets

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Tritanium", "group_id": 18}
                MockPublicClient.return_value = mock_public
                result = cmd_assets(empty_args)

        assert result.get("total_assets") == 150
        assert result.get("filtered_count") == 150
        assert len(result.get("assets", [])) == 100
        assert result.get("truncated") is True


# =============================================================================
# Fitting Command Tests
# =============================================================================


class TestFittingCommand:
    """Tests for fitting command."""

    def test_cmd_fitting_no_ship_arg(self, empty_args):
        """Test fitting command without ship argument."""
        from aria_esi.commands.assets import cmd_fitting

        empty_args.ship = None

        result = cmd_fitting(empty_args)

        assert result.get("error") == "missing_argument"
        assert "ship" in result.get("message", "").lower()

    def test_cmd_fitting_no_credentials(self, empty_args):
        """Test fitting command without credentials."""
        from aria_esi.commands.assets import cmd_fitting
        from aria_esi.core import CredentialsError

        empty_args.ship = "Rifter"

        with patch("aria_esi.commands.assets.get_authenticated_client") as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_fitting(empty_args)

        assert result.get("error") == "credentials_error"

    def test_cmd_fitting_ship_not_found(self, empty_args, mock_credentials, mock_client):
        """Test fitting command when ship not found in assets."""
        from aria_esi.commands.assets import cmd_fitting

        empty_args.ship = "Megathron"  # Ship not in assets

        # Return only a Rifter
        mock_assets = [
            {
                "item_id": 1001,
                "type_id": 587,  # Rifter
                "location_id": 60003760,
                "location_type": "station",
                "location_flag": "Hangar",
                "is_singleton": True,
                "quantity": 1,
            }
        ]

        mock_client.get.return_value = mock_assets

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.SHIP_GROUP_IDS", {25}):
                with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                    mock_public = create_mock_public_client()
                    mock_public.get_safe.return_value = {"name": "Rifter", "group_id": 25}
                    MockPublicClient.return_value = mock_public
                    result = cmd_fitting(empty_args)

        assert result.get("error") == "ship_not_found"
        assert "Megathron" in result.get("message", "")

    def test_cmd_fitting_success_by_name(
        self, empty_args, mock_credentials, mock_client, mock_fitting_assets_response
    ):
        """Test fitting command finds ship by type name."""
        from aria_esi.commands.assets import cmd_fitting

        empty_args.ship = "Rifter"

        mock_client.get.return_value = mock_fitting_assets_response

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.SHIP_GROUP_IDS", {25}):
                with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                    mock_public = create_mock_public_client()

                    def get_safe_handler(url):
                        if "/types/587" in url:
                            return {"name": "Rifter", "group_id": 25}
                        elif "/types/2046" in url:
                            return {"name": "Damage Control II", "group_id": 60}
                        elif "/types/527" in url:
                            return {"name": "1MN Afterburner I", "group_id": 46}
                        elif "/types/2881" in url:
                            return {"name": "150mm Autocannon I", "group_id": 55}
                        elif "/types/31117" in url:
                            return {"name": "Small Projectile Burst Aerator I", "group_id": 782}
                        elif "/types/2454" in url:
                            return {"name": "Hobgoblin I", "group_id": 100}
                        elif "/types/34" in url:
                            return {"name": "Tritanium", "group_id": 18}
                        elif "/stations/" in url:
                            return {"name": "Jita IV - Moon 4"}
                        return {"name": "Unknown"}

                    mock_public.get_safe.side_effect = get_safe_handler
                    MockPublicClient.return_value = mock_public
                    result = cmd_fitting(empty_args)

        assert "error" not in result
        assert result.get("ship", {}).get("type_name") == "Rifter"
        assert result.get("ship", {}).get("item_id") == 1001
        assert "eft_format" in result

    def test_cmd_fitting_success_by_item_id(
        self, empty_args, mock_credentials, mock_client, mock_fitting_assets_response
    ):
        """Test fitting command finds ship by item_id."""
        from aria_esi.commands.assets import cmd_fitting

        empty_args.ship = "1001"  # Item ID as string

        mock_client.get.return_value = mock_fitting_assets_response

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.SHIP_GROUP_IDS", {25}):
                with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                    mock_public = create_mock_public_client()
                    mock_public.get_safe.return_value = {"name": "Rifter", "group_id": 25}
                    MockPublicClient.return_value = mock_public
                    result = cmd_fitting(empty_args)

        assert "error" not in result
        assert result.get("ship", {}).get("item_id") == 1001

    def test_cmd_fitting_with_drones(
        self, empty_args, mock_credentials, mock_client, mock_fitting_assets_response
    ):
        """Test fitting command includes drone bay contents."""
        from aria_esi.commands.assets import cmd_fitting

        empty_args.ship = "Rifter"

        mock_client.get.return_value = mock_fitting_assets_response

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.SHIP_GROUP_IDS", {25}):
                with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                    mock_public = create_mock_public_client()

                    def get_safe_handler(url):
                        if "/types/587" in url:
                            return {"name": "Rifter", "group_id": 25}
                        elif "/types/2454" in url:
                            return {"name": "Hobgoblin I", "group_id": 100}
                        elif "/stations/" in url:
                            return {"name": "Jita IV"}
                        return {"name": "Module", "group_id": 60}

                    mock_public.get_safe.side_effect = get_safe_handler
                    MockPublicClient.return_value = mock_public
                    result = cmd_fitting(empty_args)

        # Check drone bay is populated
        drone_bay = result.get("fitting", {}).get("drone_bay", [])
        assert len(drone_bay) == 1
        assert drone_bay[0]["name"] == "Hobgoblin I"
        assert drone_bay[0]["quantity"] == 5

    def test_cmd_fitting_with_cargo(
        self, empty_args, mock_credentials, mock_client, mock_fitting_assets_response
    ):
        """Test fitting command includes cargo contents."""
        from aria_esi.commands.assets import cmd_fitting

        empty_args.ship = "Rifter"

        mock_client.get.return_value = mock_fitting_assets_response

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.SHIP_GROUP_IDS", {25}):
                with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                    mock_public = create_mock_public_client()

                    def get_safe_handler(url):
                        if "/types/587" in url:
                            return {"name": "Rifter", "group_id": 25}
                        elif "/types/34" in url:
                            return {"name": "Tritanium", "group_id": 18}
                        elif "/stations/" in url:
                            return {"name": "Jita IV"}
                        return {"name": "Module", "group_id": 60}

                    mock_public.get_safe.side_effect = get_safe_handler
                    MockPublicClient.return_value = mock_public
                    result = cmd_fitting(empty_args)

        # Check cargo is populated
        cargo = result.get("fitting", {}).get("cargo", [])
        assert len(cargo) == 1
        assert cargo[0]["name"] == "Tritanium"
        assert cargo[0]["quantity"] == 100

    def test_cmd_fitting_eft_format(
        self, empty_args, mock_credentials, mock_client, mock_fitting_assets_response
    ):
        """Test fitting command generates valid EFT format."""
        from aria_esi.commands.assets import cmd_fitting

        empty_args.ship = "Rifter"

        mock_client.get.return_value = mock_fitting_assets_response

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.SHIP_GROUP_IDS", {25}):
                with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                    mock_public = create_mock_public_client()

                    def get_safe_handler(url):
                        if "/types/587" in url:
                            return {"name": "Rifter", "group_id": 25}
                        elif "/types/2046" in url:
                            return {"name": "Damage Control II", "group_id": 60}
                        elif "/types/527" in url:
                            return {"name": "1MN Afterburner I", "group_id": 46}
                        elif "/types/2881" in url:
                            return {"name": "150mm Autocannon I", "group_id": 55}
                        elif "/types/31117" in url:
                            return {"name": "Small Projectile Burst Aerator I", "group_id": 782}
                        elif "/types/2454" in url:
                            return {"name": "Hobgoblin I", "group_id": 100}
                        elif "/types/34" in url:
                            return {"name": "Tritanium", "group_id": 18}
                        elif "/stations/" in url:
                            return {"name": "Jita IV"}
                        return {"name": "Unknown"}

                    mock_public.get_safe.side_effect = get_safe_handler
                    MockPublicClient.return_value = mock_public
                    result = cmd_fitting(empty_args)

        eft = result.get("eft_format", "")
        # EFT format should start with [ShipType, FitName]
        assert eft.startswith("[Rifter, ARIA Export]")
        # Should contain module names
        assert "Damage Control II" in eft or "1MN Afterburner I" in eft or "150mm Autocannon I" in eft
        # Should contain drones with quantity
        assert "Hobgoblin I x5" in eft


# =============================================================================
# Blueprints Command Tests
# =============================================================================


class TestBlueprintsCommand:
    """Tests for blueprints command."""

    def test_cmd_blueprints_no_credentials(self, empty_args):
        """Test blueprints command without credentials."""
        from aria_esi.commands.assets import cmd_blueprints
        from aria_esi.core import CredentialsError

        with patch("aria_esi.commands.assets.get_authenticated_client") as mock_get:
            mock_get.side_effect = CredentialsError("No credentials")
            result = cmd_blueprints(empty_args)

        assert result.get("error") == "credentials_error"

    def test_cmd_blueprints_empty(self, empty_args, mock_credentials, mock_client):
        """Test blueprints command with no blueprints."""
        from aria_esi.commands.assets import cmd_blueprints

        mock_client.get.return_value = []

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            result = cmd_blueprints(empty_args)

        assert result.get("bpo_count") == 0
        assert result.get("bpc_count") == 0
        assert "No blueprints" in result.get("message", "")

    def test_cmd_blueprints_success(
        self, empty_args, mock_credentials, mock_client, mock_blueprint_response
    ):
        """Test successful blueprints fetch."""
        from aria_esi.commands.assets import cmd_blueprints

        mock_client.get.return_value = mock_blueprint_response

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()

                def get_safe_handler(url):
                    if "/types/687" in url:
                        return {"name": "Rifter Blueprint"}
                    elif "/types/688" in url:
                        return {"name": "Slasher Blueprint"}
                    elif "/stations/" in url:
                        return {"name": "Jita IV - Moon 4"}
                    return {"name": "Unknown"}

                mock_public.get_safe.side_effect = get_safe_handler
                MockPublicClient.return_value = mock_public
                result = cmd_blueprints(empty_args)

        assert result.get("bpo_count") == 1
        assert result.get("bpc_count") == 1
        assert len(result.get("bpos", [])) == 1
        assert len(result.get("bpcs", [])) == 1

    def test_cmd_blueprints_bpo_vs_bpc(
        self, empty_args, mock_credentials, mock_client, mock_blueprint_response
    ):
        """Test blueprints correctly distinguishes BPO vs BPC."""
        from aria_esi.commands.assets import cmd_blueprints

        mock_client.get.return_value = mock_blueprint_response

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Blueprint"}
                MockPublicClient.return_value = mock_public
                result = cmd_blueprints(empty_args)

        # Check BPO properties
        bpos = result.get("bpos", [])
        assert len(bpos) == 1
        assert bpos[0]["type"] == "BPO"
        assert bpos[0]["material_efficiency"] == 10
        assert bpos[0]["time_efficiency"] == 20

        # Check BPC properties
        bpcs = result.get("bpcs", [])
        assert len(bpcs) == 1
        assert bpcs[0]["type"] == "BPC"
        assert bpcs[0]["runs"] == 10

    def test_cmd_blueprints_me_te_values(self, empty_args, mock_credentials, mock_client):
        """Test blueprints shows ME/TE research values correctly."""
        from aria_esi.commands.assets import cmd_blueprints

        blueprints = [
            {
                "item_id": 1001,
                "type_id": 687,
                "quantity": -1,  # BPO
                "material_efficiency": 5,
                "time_efficiency": 10,
                "runs": -1,
                "location_id": 60003760,
            },
            {
                "item_id": 1002,
                "type_id": 687,
                "quantity": -1,  # BPO (fully researched)
                "material_efficiency": 10,
                "time_efficiency": 20,
                "runs": -1,
                "location_id": 60003760,
            },
        ]

        mock_client.get.return_value = blueprints

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            with patch("aria_esi.commands.assets.ESIClient") as MockPublicClient:
                mock_public = create_mock_public_client()
                mock_public.get_safe.return_value = {"name": "Rifter Blueprint"}
                MockPublicClient.return_value = mock_public
                result = cmd_blueprints(empty_args)

        bpos = result.get("bpos", [])
        assert len(bpos) == 2
        # Check both ME/TE values are present
        me_values = [bp["material_efficiency"] for bp in bpos]
        te_values = [bp["time_efficiency"] for bp in bpos]
        assert 5 in me_values
        assert 10 in me_values
        assert 10 in te_values
        assert 20 in te_values

    def test_cmd_blueprints_esi_error(self, empty_args, mock_credentials, mock_client):
        """Test blueprints command with ESI error."""
        from aria_esi.commands.assets import cmd_blueprints
        from aria_esi.core import ESIError

        mock_client.get.side_effect = ESIError("ESI unavailable", status_code=503)

        with patch(
            "aria_esi.commands.assets.get_authenticated_client",
            return_value=(mock_client, mock_credentials),
        ):
            result = cmd_blueprints(empty_args)

        assert result.get("error") == "esi_error"
