"""
Tests for aria_esi.core.constants

Sanity checks to ensure constants are properly defined and consistent.
"""



class TestESIConfiguration:
    """Tests for ESI configuration constants."""

    def test_esi_base_url(self):
        from aria_esi.core import ESI_BASE_URL
        assert ESI_BASE_URL == "https://esi.evetech.net/latest"
        assert ESI_BASE_URL.startswith("https://")

    def test_esi_datasource(self):
        from aria_esi.core import ESI_DATASOURCE
        assert ESI_DATASOURCE == "tranquility"


class TestShipGroupIDs:
    """Tests for ship group ID constants."""

    def test_ship_groups_not_empty(self):
        from aria_esi.core import SHIP_GROUP_IDS
        assert len(SHIP_GROUP_IDS) > 0

    def test_ship_groups_are_integers(self):
        from aria_esi.core import SHIP_GROUP_IDS
        for group_id in SHIP_GROUP_IDS:
            assert isinstance(group_id, int)
            assert group_id > 0

    def test_common_ship_groups_present(self):
        from aria_esi.core import SHIP_GROUP_IDS
        # Key ship classes that should be present
        assert 25 in SHIP_GROUP_IDS    # Frigate
        assert 26 in SHIP_GROUP_IDS    # Cruiser
        assert 27 in SHIP_GROUP_IDS    # Battleship
        assert 420 in SHIP_GROUP_IDS   # Destroyer
        assert 463 in SHIP_GROUP_IDS   # Mining Barge
        assert 2001 in SHIP_GROUP_IDS  # Mining Frigate (Venture)


class TestTradeHubConfiguration:
    """Tests for trade hub constants."""

    def test_trade_hub_regions_structure(self):
        from aria_esi.core import TRADE_HUB_REGIONS
        assert "jita" in TRADE_HUB_REGIONS
        assert "amarr" in TRADE_HUB_REGIONS
        assert "dodixie" in TRADE_HUB_REGIONS
        assert "rens" in TRADE_HUB_REGIONS
        assert "hek" in TRADE_HUB_REGIONS

    def test_trade_hub_regions_have_tuples(self):
        from aria_esi.core import TRADE_HUB_REGIONS
        for hub, data in TRADE_HUB_REGIONS.items():
            assert isinstance(data, tuple)
            assert len(data) == 2
            region_id, region_name = data
            assert isinstance(region_id, str)
            assert isinstance(region_name, str)

    def test_trade_hub_stations(self):
        from aria_esi.core import TRADE_HUB_STATIONS
        # Jita station
        assert "10000002" in TRADE_HUB_STATIONS
        assert TRADE_HUB_STATIONS["10000002"] == 60003760

    def test_station_names(self):
        from aria_esi.core import STATION_NAMES
        assert 60003760 in STATION_NAMES  # Jita
        assert "Jita" in STATION_NAMES[60003760]


class TestActivityTypes:
    """Tests for industry activity type constants."""

    def test_activity_types_structure(self):
        from aria_esi.core import ACTIVITY_TYPES
        assert 1 in ACTIVITY_TYPES  # Manufacturing
        assert 3 in ACTIVITY_TYPES  # TE Research
        assert 4 in ACTIVITY_TYPES  # ME Research
        assert 5 in ACTIVITY_TYPES  # Copying
        assert 8 in ACTIVITY_TYPES  # Invention

    def test_activity_types_have_tuples(self):
        from aria_esi.core import ACTIVITY_TYPES
        for activity_id, data in ACTIVITY_TYPES.items():
            assert isinstance(data, tuple)
            assert len(data) == 2
            key, display = data
            assert isinstance(key, str)
            assert isinstance(display, str)


class TestRefTypeCategories:
    """Tests for wallet journal ref type constants."""

    def test_ref_type_categories_not_empty(self):
        from aria_esi.core import REF_TYPE_CATEGORIES
        assert len(REF_TYPE_CATEGORIES) > 0
        assert "bounty" in REF_TYPE_CATEGORIES
        assert "market" in REF_TYPE_CATEGORIES
        assert "mission" in REF_TYPE_CATEGORIES

    def test_ref_type_names_not_empty(self):
        from aria_esi.core import REF_TYPE_NAMES
        assert len(REF_TYPE_NAMES) > 0
        assert "bounty_prizes" in REF_TYPE_NAMES
        assert "market_transaction" in REF_TYPE_NAMES

    def test_income_ref_types(self):
        from aria_esi.core import INCOME_REF_TYPES
        assert "bounty_prizes" in INCOME_REF_TYPES
        assert "agent_mission_reward" in INCOME_REF_TYPES


class TestSlotOrder:
    """Tests for fitting slot order constants."""

    def test_slot_order_structure(self):
        from aria_esi.core import SLOT_ORDER
        # Low slots
        assert "LoSlot0" in SLOT_ORDER
        assert SLOT_ORDER["LoSlot0"] == 0
        # Med slots
        assert "MedSlot0" in SLOT_ORDER
        assert SLOT_ORDER["MedSlot0"] == 0
        # High slots
        assert "HiSlot0" in SLOT_ORDER
        assert SLOT_ORDER["HiSlot0"] == 0
        # Rig slots
        assert "RigSlot0" in SLOT_ORDER
        assert SLOT_ORDER["RigSlot0"] == 0

    def test_slot_order_completeness(self):
        from aria_esi.core import SLOT_ORDER
        # Should have slots 0-7 for low/med/high
        for prefix in ["LoSlot", "MedSlot", "HiSlot"]:
            for i in range(8):
                assert f"{prefix}{i}" in SLOT_ORDER
        # Rigs 0-2
        for i in range(3):
            assert f"RigSlot{i}" in SLOT_ORDER


class TestSecurityThresholds:
    """Tests for security status threshold constants."""

    def test_thresholds(self):
        from aria_esi.core import HIGH_SEC_THRESHOLD, LOW_SEC_THRESHOLD
        assert HIGH_SEC_THRESHOLD == 0.45
        assert LOW_SEC_THRESHOLD == 0.0
        assert HIGH_SEC_THRESHOLD > LOW_SEC_THRESHOLD


class TestCorpScopes:
    """Tests for corporation scope constants."""

    def test_corp_scopes_not_empty(self):
        from aria_esi.core import CORP_SCOPES
        assert len(CORP_SCOPES) > 0

    def test_corp_scopes_are_strings(self):
        from aria_esi.core import CORP_SCOPES
        for scope in CORP_SCOPES:
            assert isinstance(scope, str)
            assert "corporation" in scope

    def test_player_corp_min_id(self):
        from aria_esi.core import PLAYER_CORP_MIN_ID
        assert PLAYER_CORP_MIN_ID == 2000000
