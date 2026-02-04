"""
ARIA ESI Constants

Shared constants used across multiple ESI commands.
Consolidates previously duplicated definitions.
"""

# =============================================================================
# ESI Configuration
# =============================================================================

ESI_BASE_URL = "https://esi.evetech.net/latest"
ESI_DATASOURCE = "tranquility"

# =============================================================================
# Ship Group IDs
#
# Used for filtering assembled ships from assets.
# Group IDs from EVE's inventory type system.
# =============================================================================

SHIP_GROUP_IDS = {
    25,  # Frigate
    26,  # Cruiser
    27,  # Battleship
    28,  # Industrial
    29,  # Capsule
    30,  # Titan
    31,  # Shuttle
    237,  # Corvette
    324,  # Assault Frigate
    358,  # Heavy Assault Cruiser
    380,  # Deep Space Transport
    381,  # Elite Battleship
    419,  # Combat Battlecruiser
    420,  # Destroyer
    463,  # Mining Barge
    485,  # Dreadnought
    513,  # Freighter
    540,  # Command Ship
    541,  # Interdictor
    543,  # Exhumer
    547,  # Carrier
    659,  # Supercarrier
    830,  # Covert Ops
    831,  # Interceptor
    832,  # Logistics
    833,  # Force Recon
    834,  # Stealth Bomber
    893,  # Electronic Attack Ship
    894,  # Heavy Interdictor
    898,  # Black Ops
    900,  # Marauder
    902,  # Jump Freighter
    906,  # Combat Recon
    941,  # Industrial Command Ship
    963,  # Strategic Cruiser
    1022,  # Prototype Exploration Ship
    1201,  # Attack Battlecruiser
    1202,  # Blockade Runner
    1283,  # Expedition Frigate
    1305,  # Tactical Destroyer
    1527,  # Logistics Frigate
    1534,  # Command Destroyer
    1538,  # Force Auxiliary
    1972,  # Flag Cruiser
    2001,  # Mining Frigate (Venture!)
}

# =============================================================================
# Trade Hub Configuration
#
# Major trade hubs and their region/station IDs.
# =============================================================================

TRADE_HUB_REGIONS = {
    "jita": ("10000002", "The Forge"),
    "amarr": ("10000043", "Domain"),
    "dodixie": ("10000032", "Sinq Laison"),
    "rens": ("10000030", "Heimatar"),
    "hek": ("10000042", "Metropolis"),
}

TRADE_HUB_STATIONS = {
    "10000002": 60003760,  # Jita IV - Moon 4 - Caldari Navy Assembly Plant
    "10000043": 60008494,  # Amarr VIII (Oris) - Emperor Family Academy
    "10000032": 60011866,  # Dodixie IX - Moon 20 - Federation Navy Assembly Plant
    "10000030": 60004588,  # Rens VI - Moon 8 - Brutor Tribe Treasury
    "10000042": 60005686,  # Hek VIII - Moon 12 - Boundless Creation Factory
}

STATION_NAMES = {
    60003760: "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    60008494: "Amarr VIII (Oris) - Emperor Family Academy",
    60011866: "Dodixie IX - Moon 20 - Federation Navy Assembly Plant",
    60004588: "Rens VI - Moon 8 - Brutor Tribe Treasury",
    60005686: "Hek VIII - Moon 12 - Boundless Creation Factory",
}

# =============================================================================
# Industry Activity Types
#
# Mapping from ESI activity_id to internal key and display name.
# =============================================================================

ACTIVITY_TYPES = {
    1: ("manufacturing", "Manufacturing"),
    3: ("research_te", "TE Research"),
    4: ("research_me", "ME Research"),
    5: ("copying", "Copying"),
    7: ("reverse_engineering", "Reverse Eng"),
    8: ("invention", "Invention"),
    9: ("reactions", "Reactions"),
    11: ("reaction", "Reaction"),
}

# =============================================================================
# Wallet Journal Reference Types
#
# Categorization and display names for wallet journal entries.
# =============================================================================

REF_TYPE_CATEGORIES = {
    "bounty": [
        "bounty_prizes",
        "bounty_prize",
        "agent_mission_reward",
        "agent_mission_time_bonus_reward",
        "agent_mission_bonus_reward",
    ],
    "market": ["market_transaction", "market_escrow"],
    "industry": ["industry_job_tax", "manufacturing", "reprocessing_tax"],
    "insurance": ["insurance"],
    "transfer": [
        "player_donation",
        "player_trading",
        "corporation_account_withdrawal",
        "corporation_account_deposit",
    ],
    "tax": ["transaction_tax", "brokers_fee", "bounty_prize_corporation_tax"],
    "contract": [
        "contract_price",
        "contract_reward",
        "contract_collateral",
        "contract_deposit",
        "contract_brokers_fee",
    ],
    "mission": [
        "agent_mission_reward",
        "agent_mission_time_bonus_reward",
        "agent_mission_bonus_reward",
    ],
    "lp": ["lp_store"],
}

REF_TYPE_NAMES = {
    "bounty_prizes": "Bounties",
    "bounty_prize": "Bounties",
    "agent_mission_reward": "Mission Rewards",
    "agent_mission_time_bonus_reward": "Mission Time Bonus",
    "agent_mission_bonus_reward": "Mission Bonus",
    "market_transaction": "Market Trading",
    "market_escrow": "Market Escrow",
    "industry_job_tax": "Industry Tax",
    "manufacturing": "Manufacturing",
    "insurance": "Insurance",
    "player_donation": "Player Transfer",
    "player_trading": "Direct Trade",
    "corporation_account_withdrawal": "Corp Withdrawal",
    "corporation_account_deposit": "Corp Deposit",
    "transaction_tax": "Sales Tax",
    "brokers_fee": "Broker Fee",
    "bounty_prize_corporation_tax": "Corp Bounty Tax",
    "contract_price": "Contract Payment",
    "contract_reward": "Contract Reward",
    "contract_collateral": "Contract Collateral",
    "reprocessing_tax": "Reprocessing Tax",
    "lp_store": "LP Store",
}

# Ref types where positive amounts indicate income
INCOME_REF_TYPES = {
    "bounty_prizes",
    "bounty_prize",
    "agent_mission_reward",
    "agent_mission_time_bonus_reward",
    "agent_mission_bonus_reward",
    "insurance",
    "contract_reward",
}

# =============================================================================
# Ship Fitting Slot Mappings
#
# Maps ESI location_flag to slot position for EFT format export.
# =============================================================================

SLOT_ORDER = {
    "LoSlot0": 0,
    "LoSlot1": 1,
    "LoSlot2": 2,
    "LoSlot3": 3,
    "LoSlot4": 4,
    "LoSlot5": 5,
    "LoSlot6": 6,
    "LoSlot7": 7,
    "MedSlot0": 0,
    "MedSlot1": 1,
    "MedSlot2": 2,
    "MedSlot3": 3,
    "MedSlot4": 4,
    "MedSlot5": 5,
    "MedSlot6": 6,
    "MedSlot7": 7,
    "HiSlot0": 0,
    "HiSlot1": 1,
    "HiSlot2": 2,
    "HiSlot3": 3,
    "HiSlot4": 4,
    "HiSlot5": 5,
    "HiSlot6": 6,
    "HiSlot7": 7,
    "RigSlot0": 0,
    "RigSlot1": 1,
    "RigSlot2": 2,
}

# =============================================================================
# Security Status Thresholds
#
# Used for route planning and threat assessment.
# EVE security: high-sec >= 0.5, low-sec 0.1-0.4, null-sec <= 0.0
# =============================================================================

# Security status >= this is considered high-sec (0.45 rounds to 0.5)
HIGH_SEC_THRESHOLD = 0.45

# Security status > this is low-sec; <= this is null-sec
# Null-sec is security status 0.0 or below (includes negative values)
LOW_SEC_THRESHOLD = 0.0

# =============================================================================
# Corporation Scopes
#
# ESI scopes required for corporation operations.
# =============================================================================

CORP_SCOPES = [
    "esi-wallet.read_corporation_wallets.v1",
    "esi-assets.read_corporation_assets.v1",
    "esi-corporations.read_blueprints.v1",
    "esi-industry.read_corporation_jobs.v1",
]

# Minimum corporation ID for player corps (NPC corps are below this)
PLAYER_CORP_MIN_ID = 2000000
