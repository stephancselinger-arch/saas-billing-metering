"""
Billing models — plans, pricing, subscriptions, and invoices.

A Plan bundles a flat recurring fee with any number of metered PriceComponents.
Each component maps a Meter to a pricing model (per-unit, tiered, volume, package).
A Subscription links a customer to a plan for a billing period.
An Invoice is the aggregated result of metering a subscription over that period.
"""

from enum import Enum
from typing import Optional
from datetime import date, datetime
import uuid

from pydantic import BaseModel, Field


class PricingModel(str, Enum):
    PER_UNIT = "per_unit"   # flat price per unit, no tiers
    TIERED = "tiered"       # graduated: each tier's units priced at that tier's rate
    VOLUME = "volume"       # whole quantity priced at the single tier it lands in
    PACKAGE = "package"     # price per block of N units (rounded up)


class PriceTier(BaseModel):
    # Upper bound (inclusive) of units this tier covers. None = unbounded (last tier).
    up_to: Optional[float] = None
    unit_price_usd: float = 0.0     # price per unit within this tier
    flat_price_usd: float = 0.0     # flat fee added if any usage reaches this tier


class PriceComponent(BaseModel):
    meter_key: str
    pricing_model: PricingModel = PricingModel.PER_UNIT
    # PER_UNIT uses unit_price_usd. PACKAGE uses package_size + unit_price_usd.
    unit_price_usd: float = 0.0
    package_size: float = 1.0
    # TIERED / VOLUME use the tier ladder (ascending up_to, last tier up_to=None).
    tiers: list[PriceTier] = Field(default_factory=list)
    # Units granted free before metered pricing applies.
    free_units: float = 0.0


class Plan(BaseModel):
    id: str
    key: str
    name: str
    currency: str = "USD"
    flat_fee_usd: float = 0.0                            # recurring base fee per period
    components: list[PriceComponent] = Field(default_factory=list)


class PlanCreate(BaseModel):
    key: str
    name: str
    currency: str = "USD"
    flat_fee_usd: float = 0.0
    components: list[PriceComponent] = Field(default_factory=list)


class Customer(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    created_at: datetime


class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"


class Subscription(BaseModel):
    id: str
    customer_id: str
    plan_key: str
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    period_start: date
    period_end: date
    stripe_subscription_id: Optional[str] = None


class SubscriptionCreate(BaseModel):
    customer_id: str
    plan_key: str
    period_start: date
    period_end: date


class InvoiceLineItem(BaseModel):
    description: str
    meter_key: Optional[str] = None
    quantity: float = 0.0
    amount_usd: float = 0.0


class Invoice(BaseModel):
    id: str
    customer_id: str
    subscription_id: str
    plan_key: str
    currency: str = "USD"
    period_start: date
    period_end: date
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    subtotal_usd: float = 0.0
    total_usd: float = 0.0
    stripe_invoice_id: Optional[str] = None
    created_at: datetime


def new_plan_id() -> str:
    return f"plan_{uuid.uuid4().hex[:16]}"


def new_customer_id() -> str:
    return f"cus_{uuid.uuid4().hex[:16]}"


def new_subscription_id() -> str:
    return f"sub_{uuid.uuid4().hex[:16]}"


def new_invoice_id() -> str:
    return f"in_{uuid.uuid4().hex[:16]}"
