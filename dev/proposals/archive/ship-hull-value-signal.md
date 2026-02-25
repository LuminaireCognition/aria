# Proposal: Ship Hull Value Signal for Notification Filtering

**Date:** 2026-02-17
**Status:** Implemented
**Motivation:** Enable `#intel-exotic-losses` channel to filter on hull value only (>=1B ISK), excluding modules and cargo from the threshold.

---

## Problem

The notification interest engine has one value field: `ProcessedKill.total_value`, sourced from zKillboard's `zkb.totalValue`. This is the fitted value (hull + modules + rigs + cargo). There is no way to filter by hull value alone.

**Use case:** A 1B+ hull loss (e.g. Marauder, Black Ops, capital) is always noteworthy. A T1 destroyer with 2B in cargo is not. Current `value.min` cannot distinguish between these.

## Current Pipeline

```
RedisQ → QueuedKill → ESI fetch → ProcessedKill → Interest Engine → Notifications
                                        │
                                   total_value (only value field)
```

**ProcessedKill** stores `victim_ship_type_id` but never looks up what that hull costs.

## Proposed Solution

Add a `hull_value` field to `ProcessedKill` and a new `hull_value` signal to the interest engine.

### 1. Hull Price Source

Use **SDE adjusted base prices** via the existing EOS/SDE infrastructure, not live market orders. Rationale:

- CCP's adjusted prices update daily and track market closely enough for a 1B threshold
- No async market API calls in the hot path
- Already accessible: `sde(action="item_info")` returns `base_price`
- Deterministic — same type_id always produces same price within a day

**Implementation:** A lightweight lookup table loaded at poller startup from the SDE database. ~500 ship type_ids, cached in memory. Refresh daily or on poller restart.

```python
class ShipPriceLookup:
    """In-memory ship hull price cache from SDE adjusted prices."""
    _prices: dict[int, float]  # type_id → adjusted_price

    async def load(self) -> None:
        """Load all published ship type prices from SDE."""
        ...

    def get_hull_value(self, type_id: int) -> float | None:
        return self._prices.get(type_id)
```

### 2. ProcessedKill Extension

```python
@dataclass
class ProcessedKill:
    # ... existing fields ...
    hull_value: float | None = None  # NEW: SDE adjusted price for victim hull
```

Populated during `parse_esi_killmail()` by looking up `victim_ship_type_id` in the price cache. Zero-cost if cache is warm (dict lookup).

### 3. Database Schema

Add `hull_value REAL` column to `realtime_kills` table. Nullable for backward compatibility — existing rows get `NULL`, new kills get populated.

Migration: `ALTER TABLE realtime_kills ADD COLUMN hull_value REAL;`

### 4. Interest Engine Signal

New signal provider in `interest_v2/signals/hull_value.py`:

```python
class HullValueSignal(BaseSignalProvider):
    _name = "hull_value"
    _category = "value"
    _prefetch_capable = True  # SDE lookup is local, no async needed

    def score(self, kill, system_id, config):
        if kill.hull_value is None:
            return SignalScore(score=0.0, reason="No hull price data")

        min_val = config.get("min", 0)
        if kill.hull_value < min_val:
            return SignalScore(score=0.0, reason=f"Hull {fmt_isk(kill.hull_value)} < {fmt_isk(min_val)}")

        return scale_value(kill.hull_value, config)
```

### 5. Profile Configuration

```yaml
# userdata/notifications/exotic-losses.yaml
interest:
  signals:
    hull_value:
      min: 1000000000  # 1B ISK hull only
      scale: sigmoid
      pivot: 2000000000
```

Compatible with existing signal architecture. Can be combined with other signals (location, ship class, etc.) using standard aggregation.

## Scope & Effort

| Component | Files Changed | Complexity |
|-----------|---------------|------------|
| ShipPriceLookup service | 1 new | Low |
| ProcessedKill + parser | 2 modified | Low |
| DB migration | 1 modified | Low |
| HullValueSignal | 1 new | Low |
| Signal registration | 1 modified | Low |
| Profile schema docs | 1 modified | Low |
| Tests | 2-3 new/modified | Medium |

**Estimated total: ~8 files touched, no architectural changes.**

The key insight is that SDE adjusted prices make this a local lookup, not an async market call. That keeps it prefetch-capable and avoids rate limiting or latency concerns in the notification hot path.

## What This Does NOT Do

- **Module-level breakdown**: We don't decompose fitted value into hull vs modules vs cargo. We only add the hull's SDE price as a separate field.
- **Live market prices**: We use SDE adjusted prices, not Jita sell orders. For a 1B threshold this is accurate enough.
- **Cargo filtering**: Cargo value remains unknowable from zKillboard's aggregate data without fetching full ESI killmail items (out of scope).

## Alternatives Considered

| Alternative | Why Not |
|-------------|---------|
| `fittedValue` threshold | Still includes modules, doesn't meet requirement |
| Ship class allowlist (capitals only) | Too coarse — misses Marauders, Black Ops, pirate BS |
| `totalValue - hull_value` for module estimate | Interesting but not needed for this use case |
| Live market prices | Unnecessary complexity for threshold filtering |
