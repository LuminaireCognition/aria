"""
ARIA ESI - EVE Online ESI API Interface

A modular Python package for accessing EVE Online's ESI API.
Provides both library access and CLI commands.

Usage as library:
    from aria_esi.core import ESIClient, get_credentials

    # Public (unauthenticated) queries
    client = ESIClient()
    system_info = client.get_system_info(30000142)  # Jita

    # Authenticated queries
    creds = get_credentials()
    client = ESIClient(token=creds.access_token)
    location = client.get("/characters/{}/location/".format(creds.character_id), auth=True)

Usage as CLI:
    python -m aria_esi route Dodixie Jita
    python -m aria_esi price Tritanium --jita
    python -m aria_esi location

Package structure:
    aria_esi/
    ├── core/           # Shared infrastructure
    │   ├── client.py   # ESI HTTP client
    │   ├── auth.py     # Credential management
    │   ├── constants.py # Shared constants
    │   └── formatters.py # Output formatters
    ├── commands/       # CLI command implementations
    └── models/         # Data structures
"""

__version__ = "1.0.0"
__author__ = "ARIA Tactical Systems"

# Re-export commonly used classes for convenience
from .core import (
    Credentials,
    CredentialsError,
    ESIClient,
    ESIError,
    get_credentials,
    get_utc_timestamp,
)

__all__ = [
    "__version__",
    "ESIClient",
    "ESIError",
    "Credentials",
    "CredentialsError",
    "get_credentials",
    "get_utc_timestamp",
]
