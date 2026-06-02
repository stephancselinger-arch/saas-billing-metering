"""
Usage event store — ingests metered usage and aggregates it per meter.

In production this would be a time-series / columnar store (ClickHouse,
Timescale) with the same interface. Here we use an in-memory list so the
service runs with zero dependencies; swap the backend without touching routers.
"""

from datetime import datetime, timezone, date
from typing import Optional

from app.models.metering import (
    Meter, MeterCreate, UsageEvent, UsageEventCreate, Aggregation,
    new_meter_id, new_event_id,
)


_meters: dict[str, Meter] = {}
_events: list[UsageEvent] = []
_seen_idempotency_keys: set[str] = set()


# ---- Meters ---------------------------------------------------------------

def create_meter(data: MeterCreate) -> Meter:
    if data.key in _meters:
        raise ValueError(f"Meter with key '{data.key}' already exists")
    meter = Meter(id=new_meter_id(), **data.model_dump())
    _meters[meter.key] = meter
    return meter


def get_meter(key: str) -> Optional[Meter]:
    return _meters.get(key)


def list_meters() -> list[Meter]:
    return list(_meters.values())


# ---- Usage events ---------------------------------------------------------

def ingest(batch: list[UsageEventCreate]) -> dict:
    accepted = 0
    duplicates = 0
    for ev in batch:
        if ev.meter_key not in _meters:
            raise ValueError(f"Unknown meter_key '{ev.meter_key}'")
        if ev.idempotency_key and ev.idempotency_key in _seen_idempotency_keys:
            duplicates += 1
            continue
        if ev.idempotency_key:
            _seen_idempotency_keys.add(ev.idempotency_key)
        _events.append(UsageEvent(
            id=new_event_id(),
            customer_id=ev.customer_id,
            meter_key=ev.meter_key,
            quantity=ev.quantity,
            timestamp=ev.timestamp or datetime.now(timezone.utc),
            idempotency_key=ev.idempotency_key,
            properties=ev.properties,
        ))
        accepted += 1
    return {"accepted": accepted, "duplicates": duplicates, "total_events": len(_events)}


def query(
    customer_id: Optional[str] = None,
    meter_key: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[UsageEvent]:
    results = _events
    if customer_id:
        results = [e for e in results if e.customer_id == customer_id]
    if meter_key:
        results = [e for e in results if e.meter_key == meter_key]
    if date_from:
        results = [e for e in results if e.timestamp.date() >= date_from]
    if date_to:
        results = [e for e in results if e.timestamp.date() <= date_to]
    return results


def aggregate(
    customer_id: str,
    meter_key: str,
    date_from: date,
    date_to: date,
) -> float:
    """Collapse a customer's events for one meter into a billable quantity."""
    meter = _meters.get(meter_key)
    if meter is None:
        raise ValueError(f"Unknown meter_key '{meter_key}'")

    events = query(customer_id=customer_id, meter_key=meter_key,
                   date_from=date_from, date_to=date_to)
    if not events:
        return 0.0

    if meter.aggregation == Aggregation.SUM:
        return sum(e.quantity for e in events)
    if meter.aggregation == Aggregation.MAX:
        return max(e.quantity for e in events)
    if meter.aggregation == Aggregation.LAST:
        return sorted(events, key=lambda e: e.timestamp)[-1].quantity
    if meter.aggregation == Aggregation.UNIQUE:
        prop = meter.unique_property or "value"
        return float(len({e.properties.get(prop) for e in events if prop in e.properties}))
    return 0.0


def total_event_count() -> int:
    return len(_events)


def reset() -> None:
    """Test helper — clears all in-memory state."""
    _meters.clear()
    _events.clear()
    _seen_idempotency_keys.clear()
