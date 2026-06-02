"""
Metering models — the raw usage signals that drive usage-based billing.

A Meter defines *what* is billable (api_calls, gb_storage, compute_seconds)
and *how* raw events roll up into a billable quantity (sum, max, last, unique).
A UsageEvent is a single recorded unit of consumption for a customer.
"""

from enum import Enum
from typing import Optional
from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class Aggregation(str, Enum):
    """How raw usage events collapse into one billable quantity per period."""
    SUM = "sum"              # total units consumed (api calls, messages sent)
    MAX = "max"             # peak value in the period (max seats, peak storage)
    LAST = "last"           # last reported value (current storage GB)
    UNIQUE = "unique"       # count of distinct values (monthly active users)


class Meter(BaseModel):
    id: str
    key: str                                    # stable code used when recording events, e.g. "api_calls"
    display_name: str
    unit: str = "unit"                          # human label: "calls", "GB", "seconds"
    aggregation: Aggregation = Aggregation.SUM
    # For UNIQUE aggregation, the event property whose distinct values are counted.
    unique_property: Optional[str] = None


class MeterCreate(BaseModel):
    key: str
    display_name: str
    unit: str = "unit"
    aggregation: Aggregation = Aggregation.SUM
    unique_property: Optional[str] = None


class UsageEvent(BaseModel):
    id: str
    customer_id: str
    meter_key: str
    quantity: float = 1.0
    timestamp: datetime
    # Idempotency key — repeated ingest of the same key is recorded once.
    idempotency_key: Optional[str] = None
    # Free-form dimensions (region, sku, the value counted by UNIQUE meters, etc.)
    properties: dict[str, str] = Field(default_factory=dict)


class UsageEventCreate(BaseModel):
    customer_id: str
    meter_key: str
    quantity: float = 1.0
    timestamp: Optional[datetime] = None        # defaults to ingest time if omitted
    idempotency_key: Optional[str] = None
    properties: dict[str, str] = Field(default_factory=dict)


def new_meter_id() -> str:
    return f"mtr_{uuid.uuid4().hex[:16]}"


def new_event_id() -> str:
    return f"evt_{uuid.uuid4().hex[:16]}"
