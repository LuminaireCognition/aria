# ESI Fixture Files

This directory contains externalized ESI API response fixtures for testing.

## Directory Structure

```
esi/
├── character/          # Character-specific ESI responses
│   ├── info.json       # GET /characters/{character_id}/
│   ├── location.json   # GET /characters/{character_id}/location/
│   └── wallet.json     # GET /characters/{character_id}/wallet/
├── killmails/          # Killmail data
│   └── recent_loss.json
└── universe/           # Universe data
    └── system_jita.json
```

## Conventions

### File Naming

- Use snake_case for file names
- Include identifying info: `system_jita.json`, `type_hobgoblin.json`
- For lists, use plural: `orders.json`, `skills.json`

### Data Format

- All fixtures are valid JSON matching ESI response schemas
- Use realistic test data (real type IDs, system IDs, etc.)
- Include comments via a `_comment` field if needed (will be ignored)

### Usage

```python
from tests.conftest import load_esi_fixture

def test_something():
    location = load_esi_fixture("character/location.json")
    assert location["solar_system_id"] == 30000142

# Or via fixture
def test_with_fixture(esi_fixture_loader):
    wallet = esi_fixture_loader("character/wallet.json")
```

## Adding New Fixtures

1. Create JSON file in appropriate subdirectory
2. Use actual ESI response format (check ESI Swagger docs)
3. Use test character ID 12345678 for character-specific data
4. Document any non-obvious test data in this README

## Reference IDs

Common IDs used in test fixtures:

| Entity | ID | Notes |
|--------|-----|-------|
| Test Character | 12345678 | Standard test pilot |
| Jita | 30000142 | Trade hub system |
| Jita 4-4 Station | 60003760 | Caldari Navy Assembly Plant |
| Rifter | 587 | Common test ship |
| Hobgoblin I | 2454 | Common test drone |
| Tritanium | 34 | Basic mineral |
