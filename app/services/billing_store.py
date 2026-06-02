"""
Billing store — plans, customers, subscriptions, and generated invoices.

In-memory for dev; same interface a PostgreSQL-backed repository would expose.
"""

from datetime import datetime, timezone
from typing import Optional

from app.models.billing import (
    Plan, PlanCreate, Customer, CustomerCreate,
    Subscription, SubscriptionCreate, SubscriptionStatus, Invoice,
    new_plan_id, new_customer_id, new_subscription_id,
)


_plans: dict[str, Plan] = {}
_customers: dict[str, Customer] = {}
_subscriptions: dict[str, Subscription] = {}
_invoices: dict[str, Invoice] = {}


# ---- Plans ----------------------------------------------------------------

def create_plan(data: PlanCreate) -> Plan:
    if data.key in _plans:
        raise ValueError(f"Plan with key '{data.key}' already exists")
    plan = Plan(id=new_plan_id(), **data.model_dump())
    _plans[plan.key] = plan
    return plan


def get_plan(key: str) -> Optional[Plan]:
    return _plans.get(key)


def list_plans() -> list[Plan]:
    return list(_plans.values())


# ---- Customers ------------------------------------------------------------

def create_customer(data: CustomerCreate, stripe_customer_id: Optional[str] = None) -> Customer:
    customer = Customer(
        id=new_customer_id(),
        name=data.name,
        email=data.email,
        stripe_customer_id=stripe_customer_id,
        created_at=datetime.now(timezone.utc),
    )
    _customers[customer.id] = customer
    return customer


def get_customer(customer_id: str) -> Optional[Customer]:
    return _customers.get(customer_id)


def list_customers() -> list[Customer]:
    return list(_customers.values())


# ---- Subscriptions --------------------------------------------------------

def create_subscription(
    data: SubscriptionCreate,
    stripe_subscription_id: Optional[str] = None,
) -> Subscription:
    sub = Subscription(
        id=new_subscription_id(),
        customer_id=data.customer_id,
        plan_key=data.plan_key,
        period_start=data.period_start,
        period_end=data.period_end,
        stripe_subscription_id=stripe_subscription_id,
    )
    _subscriptions[sub.id] = sub
    return sub


def get_subscription(subscription_id: str) -> Optional[Subscription]:
    return _subscriptions.get(subscription_id)


def list_subscriptions(customer_id: Optional[str] = None) -> list[Subscription]:
    subs = list(_subscriptions.values())
    if customer_id:
        subs = [s for s in subs if s.customer_id == customer_id]
    return subs


def cancel_subscription(subscription_id: str) -> Optional[Subscription]:
    sub = _subscriptions.get(subscription_id)
    if sub:
        sub.status = SubscriptionStatus.CANCELED
    return sub


# ---- Invoices -------------------------------------------------------------

def save_invoice(invoice: Invoice) -> Invoice:
    _invoices[invoice.id] = invoice
    return invoice


def get_invoice(invoice_id: str) -> Optional[Invoice]:
    return _invoices.get(invoice_id)


def list_invoices(customer_id: Optional[str] = None) -> list[Invoice]:
    invoices = list(_invoices.values())
    if customer_id:
        invoices = [i for i in invoices if i.customer_id == customer_id]
    return invoices


def reset() -> None:
    """Test helper — clears all in-memory state."""
    _plans.clear()
    _customers.clear()
    _subscriptions.clear()
    _invoices.clear()
