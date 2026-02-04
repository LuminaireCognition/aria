# STP-002: Response Models (Pydantic)

**Status:** Complete
**Priority:** P0 - Foundation
**Depends On:** None
**Blocks:** STP-005 through STP-010

## Objective

Implement Pydantic models for type-safe, serializable MCP tool responses. These models define the API contract between the MCP server and Claude.

## Scope

### In Scope
- All response models from design document
- Field validation and constraints
- JSON serialization configuration
- Docstrings for MCP tool descriptions

### Out of Scope
- Request validation (handled by MCP SDK)
- Error response models (STP-004)

## File Location

```
aria_esi/mcp/models.py
```

## Implementation

### Base Configuration

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

class MCPModel(BaseModel):
    """Base model with MCP-friendly serialization."""
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        ser_json_inf_nan="constants"
    )
```

### NeighborInfo

```python
class NeighborInfo(MCPModel):
    """Adjacent system summary."""
    name: str
    security: float = Field(ge=-1.0, le=1.0)
    security_class: Literal["HIGH", "LOW", "NULL"]
```

### SystemInfo

```python
class SystemInfo(MCPModel):
    """Complete system information."""
    name: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    security_class: Literal["HIGH", "LOW", "NULL"]
    constellation: str
    constellation_id: int
    region: str
    region_id: int
    neighbors: list[NeighborInfo]
    is_border: bool = Field(description="High-sec system adjacent to low-sec")
    adjacent_lowsec: list[str] = Field(default_factory=list)
```

### SecuritySummary

```python
class SecuritySummary(MCPModel):
    """Route security breakdown."""
    total_jumps: int = Field(ge=0)
    highsec_jumps: int = Field(ge=0)
    lowsec_jumps: int = Field(ge=0)
    nullsec_jumps: int = Field(ge=0)
    lowest_security: float = Field(ge=-1.0, le=1.0)
    lowest_security_system: str
```

### RouteResult

```python
class RouteResult(MCPModel):
    """Complete route with analysis."""
    origin: str
    destination: str
    mode: Literal["shortest", "safe", "unsafe"]
    jumps: int = Field(ge=0)
    systems: list[SystemInfo]
    security_summary: SecuritySummary
    warnings: list[str] = Field(default_factory=list)
```

### BorderSystem

```python
class BorderSystem(MCPModel):
    """Border system with distance info."""
    name: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    jumps_from_origin: int = Field(ge=0)
    adjacent_lowsec: list[str]
    region: str
```

### LoopResult

```python
class LoopResult(MCPModel):
    """Circular route through border systems."""
    systems: list[SystemInfo]
    total_jumps: int = Field(ge=0)
    unique_systems: int = Field(ge=0)
    border_systems_visited: list[BorderSystem]
    backtrack_jumps: int = Field(ge=0)
    efficiency: float = Field(ge=0.0, le=1.0)
```

### RouteAnalysis

```python
class DangerZone(MCPModel):
    """Consecutive dangerous segment."""
    start_system: str
    end_system: str
    jump_count: int = Field(ge=1)
    min_security: float

class RouteAnalysis(MCPModel):
    """Detailed security analysis of a route."""
    systems: list[SystemInfo]
    security_summary: SecuritySummary
    chokepoints: list[SystemInfo] = Field(
        default_factory=list,
        description="Low-sec entry/exit points"
    )
    danger_zones: list[DangerZone] = Field(
        default_factory=list,
        description="Consecutive low/null segments"
    )
    safest_alternative: RouteResult | None = None
```

### Search/Query Results

```python
class SystemSearchResult(MCPModel):
    """System matching search criteria."""
    name: str
    system_id: int
    security: float
    security_class: Literal["HIGH", "LOW", "NULL"]
    region: str
    jumps_from_origin: int | None = None

class BorderSearchResult(MCPModel):
    """Border system search result."""
    systems: list[BorderSystem]
    search_origin: str
    max_jumps_searched: int
    total_found: int
```

## Dependencies

```toml
# pyproject.toml - already present
pydantic = ">=2.0.0"
```

## Acceptance Criteria

1. [x] All models defined with correct field types
2. [x] Field validation constraints applied (ge, le, etc.)
3. [x] Models serialize to JSON without errors
4. [x] Frozen models prevent accidental mutation
5. [x] Docstrings describe each model's purpose
6. [x] Module exports all models from `aria_esi.mcp.models`

## Test Requirements

```python
# tests/mcp/test_models.py

def test_system_info_serialization():
    """SystemInfo serializes to valid JSON."""
    info = SystemInfo(
        name="Jita",
        system_id=30000142,
        security=0.9,
        security_class="HIGH",
        constellation="Kimotoro",
        constellation_id=20000001,
        region="The Forge",
        region_id=10000002,
        neighbors=[],
        is_border=False
    )
    json_str = info.model_dump_json()
    assert "Jita" in json_str

def test_security_field_validation():
    """Security values validated within [-1, 1]."""
    with pytest.raises(ValidationError):
        SystemInfo(security=1.5, ...)  # Out of range

def test_route_result_nested_serialization():
    """Nested models serialize correctly."""
    route = RouteResult(
        origin="Jita",
        destination="Amarr",
        mode="shortest",
        jumps=10,
        systems=[...],
        security_summary=SecuritySummary(...)
    )
    data = route.model_dump()
    assert "security_summary" in data
    assert isinstance(data["security_summary"], dict)

def test_models_are_frozen():
    """Models reject attribute modification."""
    info = NeighborInfo(name="Jita", security=0.9, security_class="HIGH")
    with pytest.raises(ValidationError):
        info.name = "Amarr"
```

## Estimated Effort

- Implementation: Small
- Testing: Small
- Total: Small

## Notes

- Using `frozen=True` prevents accidental mutation and enables hashing
- `extra="forbid"` catches typos in field names during construction
- Consider adding `__repr__` overrides for better debugging output
