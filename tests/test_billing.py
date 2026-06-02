import pytest
from datetime import datetime, timezone, date, timedelta

from app.models.metering import MeterCreate, UsageEventCreate, Aggregation
from app.models.billing import (
    PlanCreate, PriceComponent, PriceTier, PricingModel,
    CustomerCreate, SubscriptionCreate,
)
from app.services import meter_store, billing_store, billing_engine
from app.services.stripe_client import StripeClient


@pytest.fixture(autouse=True)
def clean_stores():
    meter_store.reset()
    billing_store.reset()
    yield
    meter_store.reset()
    billing_store.reset()


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def _period():
    today = datetime.now(timezone.utc).date()
    return today, today + timedelta(days=30)


def _setup_plan_with_usage():
    """Plan: $50 base + tiered api_calls. Customer with 5000 calls logged."""
    meter_store.create_meter(MeterCreate(key="api_calls", display_name="API Calls",
                                         unit="calls", aggregation=Aggregation.SUM))
    plan = billing_store.create_plan(PlanCreate(
        key="growth",
        name="Growth Plan",
        flat_fee_usd=50.0,
        components=[PriceComponent(
            meter_key="api_calls",
            pricing_model=PricingModel.TIERED,
            free_units=1_000,
            tiers=[
                PriceTier(up_to=10_000, unit_price_usd=0.01),
                PriceTier(up_to=None, unit_price_usd=0.005),
            ],
        )],
    ))
    customer = billing_store.create_customer(CustomerCreate(name="Acme Inc", email="ap@acme.test"))
    start, end = _period()
    sub = billing_store.create_subscription(SubscriptionCreate(
        customer_id=customer.id, plan_key=plan.key, period_start=start, period_end=end,
    ))
    meter_store.ingest([
        UsageEventCreate(customer_id=customer.id, meter_key="api_calls", quantity=5_000, timestamp=_ts()),
    ])
    return customer, sub


def test_preview_invoice_totals():
    customer, sub = _setup_plan_with_usage()
    invoice = billing_engine.preview_invoice(sub.id)

    # base 50 + tiered: (5000 - 1000 free) = 4000 @ 0.01 = 40 → total 90
    assert invoice.total_usd == pytest.approx(90.0)
    assert invoice.subtotal_usd == pytest.approx(90.0)
    assert len(invoice.line_items) == 2
    assert invoice.stripe_invoice_id is None  # preview never touches Stripe


def test_preview_does_not_persist():
    _, sub = _setup_plan_with_usage()
    billing_engine.preview_invoice(sub.id)
    assert billing_store.list_invoices() == []


def test_generate_invoice_persists_and_bills_stripe():
    customer, sub = _setup_plan_with_usage()
    invoice = billing_engine.generate_invoice(sub.id, push_to_stripe=True)

    assert invoice.total_usd == pytest.approx(90.0)
    assert invoice.stripe_invoice_id is not None
    assert billing_store.get_invoice(invoice.id) is not None
    assert billing_store.list_invoices(customer_id=customer.id)[0].id == invoice.id


def test_generate_invoice_without_stripe():
    _, sub = _setup_plan_with_usage()
    invoice = billing_engine.generate_invoice(sub.id, push_to_stripe=False)
    assert invoice.stripe_invoice_id is None


def test_unknown_subscription_raises():
    with pytest.raises(ValueError):
        billing_engine.preview_invoice("sub_does_not_exist")


def test_flat_fee_only_when_no_usage():
    meter_store.create_meter(MeterCreate(key="api_calls", display_name="API Calls"))
    plan = billing_store.create_plan(PlanCreate(
        key="starter", name="Starter", flat_fee_usd=9.0,
        components=[PriceComponent(meter_key="api_calls", unit_price_usd=0.01)],
    ))
    customer = billing_store.create_customer(CustomerCreate(name="NoUsage Co"))
    start, end = _period()
    sub = billing_store.create_subscription(SubscriptionCreate(
        customer_id=customer.id, plan_key=plan.key, period_start=start, period_end=end,
    ))
    invoice = billing_engine.preview_invoice(sub.id)
    assert invoice.total_usd == pytest.approx(9.0)


def test_stripe_client_mock_mode_records_calls():
    client = StripeClient(api_key="")  # force mock
    assert client.live is False
    cid = client.create_customer("Test", "t@test.io")
    assert cid.startswith("cus_mock_")
    inv = client.create_invoice(cid, 123.45, "test invoice")
    assert inv.startswith("in_mock_")
    actions = [c["action"] for c in client.mock_calls]
    assert "create_customer" in actions
    assert "create_invoice" in actions
    # amount converted to cents
    invoice_call = next(c for c in client.mock_calls if c["action"] == "create_invoice")
    assert invoice_call["amount_cents"] == 12345
