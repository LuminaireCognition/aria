"""
Shared fixtures for command module tests.

Provides mock credentials, ESI clients, and common response data.
"""

import argparse
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# =============================================================================
# Mock Client Factory
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
# Credential Fixtures
# =============================================================================


@pytest.fixture
def mock_credentials():
    """Create mock credentials for testing."""
    from aria_esi.core import Credentials

    creds = MagicMock(spec=Credentials)
    creds.character_id = 12345678
    creds.character_name = "Test Pilot"
    creds.is_expired = False
    creds.scopes = [
        "esi-characters.read_agents_research.v1",
        "esi-location.read_location.v1",
        "esi-characters.read_standings.v1",
        "esi-wallet.read_character_wallet.v1",
        "esi-wallet.read_corporation_wallets.v1",
        "esi-assets.read_corporation_assets.v1",
        "esi-corporations.read_blueprints.v1",
        "esi-industry.read_corporation_jobs.v1",
        "esi-markets.read_character_orders.v1",
        "esi-mail.read_mail.v1",
        "esi-characters.read_loyalty.v1",
    ]

    def has_scope_impl(scope):
        return scope in creds.scopes

    creds.has_scope.side_effect = has_scope_impl
    return creds


@pytest.fixture
def mock_authenticated_client(mock_credentials):
    """Create mock authenticated ESI client with credentials."""
    mock_client = MagicMock()
    mock_client.get.return_value = []
    mock_client.get_dict.return_value = {}
    mock_client.get_list.return_value = []
    mock_client.get_safe.return_value = None
    mock_client.get_dict_safe.side_effect = lambda *a, **kw: mock_client.get_safe(*a, **kw) or {}
    mock_client.get_list_safe.side_effect = lambda *a, **kw: mock_client.get_safe(*a, **kw) or []
    return mock_client, mock_credentials


# =============================================================================
# Argument Fixtures
# =============================================================================


@pytest.fixture
def empty_args():
    """Create empty argparse namespace for simple commands."""
    return argparse.Namespace()


@pytest.fixture
def corp_info_args():
    """Create args for corp info command with default target."""
    args = argparse.Namespace()
    args.target = "my"
    return args


@pytest.fixture
def corp_wallet_args():
    """Create args for corp wallet command."""
    args = argparse.Namespace()
    args.journal = False
    args.division = 1
    args.limit = 25
    return args


@pytest.fixture
def corp_assets_args():
    """Create args for corp assets command."""
    args = argparse.Namespace()
    args.ships = False
    args.location_filter = None
    args.type_filter = None
    return args


@pytest.fixture
def corp_blueprints_args():
    """Create args for corp blueprints command."""
    args = argparse.Namespace()
    args.filter = None
    args.bpos = False
    args.bpcs = False
    return args


@pytest.fixture
def corp_jobs_args():
    """Create args for corp jobs command."""
    args = argparse.Namespace()
    args.active = False
    args.completed = False
    args.history = False
    return args


@pytest.fixture
def mail_args():
    """Create args for mail command."""
    args = argparse.Namespace()
    args.mail_id = None
    args.unread = False
    args.limit = 50
    return args


@pytest.fixture
def orders_args():
    """Create args for orders command."""
    args = argparse.Namespace()
    args.history = False
    return args


@pytest.fixture
def loyalty_args():
    """Create args for loyalty command."""
    args = argparse.Namespace()
    return args


# =============================================================================
# Mock ESI Response Data
# =============================================================================


@pytest.fixture
def mock_research_agents_response():
    """Sample research agents ESI response."""
    return [
        {
            "agent_id": 3019003,
            "skill_type_id": 11433,  # Mechanical Engineering
            "started_at": "2025-12-01T00:00:00Z",
            "points_per_day": 37.5,
            "remainder_points": 150.0,
        },
        {
            "agent_id": 3019004,
            "skill_type_id": 11442,  # Rocket Science
            "started_at": "2025-11-01T00:00:00Z",
            "points_per_day": 45.0,
            "remainder_points": 200.0,
        },
    ]


@pytest.fixture
def mock_character_info():
    """Mock character public info."""
    return {
        "name": "Test Pilot",
        "corporation_id": 98000001,
        "birthday": "2020-01-01T00:00:00Z",
        "race_id": 1,
        "bloodline_id": 1,
        "gender": "male",
        "security_status": 1.5,
    }


@pytest.fixture
def mock_location_response():
    """Mock character location response."""
    return {
        "solar_system_id": 30000142,
        "station_id": 60003760,
    }


@pytest.fixture
def mock_ship_response():
    """Mock character ship response."""
    return {
        "ship_item_id": 123456789,
        "ship_name": "Test Ship",
        "ship_type_id": 587,  # Rifter
    }


@pytest.fixture
def mock_standings_response():
    """Mock standings response."""
    return [
        {"from_id": 500001, "from_type": "faction", "standing": 3.5},
        {"from_id": 1000125, "from_type": "npc_corp", "standing": 2.0},
        {"from_id": 3019003, "from_type": "agent", "standing": 5.0},
    ]


@pytest.fixture
def mock_corporation_info():
    """Mock corporation public info."""
    return {
        "name": "Test Corporation",
        "ticker": "TST",
        "member_count": 50,
        "ceo_id": 12345678,
        "tax_rate": 0.10,
        "date_founded": "2020-01-01T00:00:00Z",
        "alliance_id": None,
        "home_station_id": 60003760,
        "description": "A test corporation",
    }


@pytest.fixture
def mock_corp_wallets_response():
    """Mock corporation wallet balances."""
    return [
        {"division": 1, "balance": 100000000.0},
        {"division": 2, "balance": 50000000.0},
        {"division": 3, "balance": 25000000.0},
    ]


@pytest.fixture
def mock_corp_assets_response():
    """Mock corporation assets response."""
    return [
        {
            "item_id": 1001,
            "type_id": 587,  # Rifter
            "location_id": 60003760,
            "location_type": "station",
            "location_flag": "CorpSAG1",
            "is_singleton": True,
            "quantity": 1,
        },
        {
            "item_id": 1002,
            "type_id": 34,  # Tritanium
            "location_id": 60003760,
            "location_type": "station",
            "location_flag": "CorpSAG1",
            "is_singleton": False,
            "quantity": 100000,
        },
    ]


@pytest.fixture
def mock_corp_blueprints_response():
    """Mock corporation blueprints response."""
    return [
        {
            "item_id": 2001,
            "type_id": 687,  # Rifter Blueprint
            "quantity": -1,  # BPO
            "material_efficiency": 10,
            "time_efficiency": 20,
            "runs": -1,
            "location_id": 60003760,
            "location_flag": "CorpSAG1",
        },
        {
            "item_id": 2002,
            "type_id": 688,  # Slasher Blueprint
            "quantity": -2,  # BPC
            "material_efficiency": 0,
            "time_efficiency": 0,
            "runs": 10,
            "location_id": 60003760,
            "location_flag": "CorpSAG1",
        },
    ]


@pytest.fixture
def mock_corp_jobs_response():
    """Mock corporation industry jobs response."""
    # Future end date for active job
    future_end = (datetime.now(timezone.utc).replace(microsecond=0) +
                  __import__("datetime").timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    past_end = "2026-01-20T12:00:00Z"

    return [
        {
            "job_id": 3001,
            "installer_id": 12345678,
            "activity_id": 1,  # Manufacturing
            "blueprint_type_id": 687,
            "product_type_id": 587,  # Rifter
            "runs": 10,
            "status": "active",
            "start_date": "2026-01-23T12:00:00Z",
            "end_date": future_end,
        },
        {
            "job_id": 3002,
            "installer_id": 12345678,
            "activity_id": 3,  # Time Efficiency Research
            "blueprint_type_id": 687,
            "runs": 1,
            "status": "delivered",
            "start_date": "2026-01-19T12:00:00Z",
            "end_date": past_end,
        },
    ]


@pytest.fixture
def mock_mail_headers_response():
    """Mock mail headers response."""
    return [
        {
            "mail_id": 1001,
            "from": 99999999,
            "subject": "Test Mail 1",
            "timestamp": "2026-01-23T12:00:00Z",
            "is_read": True,
            "labels": [1],
            "recipients": [{"recipient_id": 12345678, "recipient_type": "character"}],
        },
        {
            "mail_id": 1002,
            "from": 88888888,
            "subject": "Unread Test Mail",
            "timestamp": "2026-01-24T00:00:00Z",
            "is_read": False,
            "labels": [1],
            "recipients": [{"recipient_id": 12345678, "recipient_type": "character"}],
        },
    ]


@pytest.fixture
def mock_mail_body_response():
    """Mock single mail body response."""
    return {
        "body": "This is the mail body content.\n\nWith multiple lines.",
        "from": 99999999,
        "subject": "Test Mail 1",
        "timestamp": "2026-01-23T12:00:00Z",
        "read": True,
        "labels": [1],
        "recipients": [{"recipient_id": 12345678, "recipient_type": "character"}],
    }


@pytest.fixture
def mock_orders_response():
    """Mock character market orders response."""
    return [
        {
            "order_id": 4001,
            "type_id": 34,  # Tritanium
            "location_id": 60003760,
            "region_id": 10000002,
            "price": 5.50,
            "volume_total": 10000,
            "volume_remain": 5000,
            "is_buy_order": False,
            "issued": "2026-01-20T12:00:00Z",
            "duration": 90,
            "min_volume": 1,
            "range": "station",
            "escrow": None,
        },
        {
            "order_id": 4002,
            "type_id": 35,  # Pyerite
            "location_id": 60003760,
            "region_id": 10000002,
            "price": 10.00,
            "volume_total": 5000,
            "volume_remain": 5000,
            "is_buy_order": True,
            "issued": "2026-01-21T12:00:00Z",
            "duration": 90,
            "min_volume": 1,
            "range": "station",
            "escrow": 50000.0,
        },
    ]


@pytest.fixture
def mock_loyalty_points_response():
    """Mock character loyalty points response."""
    return [
        {"corporation_id": 1000125, "loyalty_points": 50000},
        {"corporation_id": 1000182, "loyalty_points": 25000},
    ]


@pytest.fixture
def mock_type_info_tritanium():
    """Mock type info for Tritanium."""
    return {"type_id": 34, "name": "Tritanium", "group_id": 18}


@pytest.fixture
def mock_type_info_pyerite():
    """Mock type info for Pyerite."""
    return {"type_id": 35, "name": "Pyerite", "group_id": 18}


@pytest.fixture
def mock_type_info_rifter():
    """Mock type info for Rifter."""
    return {"type_id": 587, "name": "Rifter", "group_id": 25}


@pytest.fixture
def mock_station_info():
    """Mock station info for Jita 4-4."""
    return {
        "station_id": 60003760,
        "name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
        "system_id": 30000142,
    }


@pytest.fixture
def mock_system_info_jita():
    """Mock system info for Jita."""
    return {
        "system_id": 30000142,
        "name": "Jita",
        "security_status": 0.9459,
    }
