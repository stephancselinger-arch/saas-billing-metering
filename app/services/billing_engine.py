"""
Billing engine — turns a subscription's metered usage into an invoice.

For a given subscription it:
  1. loads the plan,
  2. aggregates each metered component's usage over the billing period,
  3. prices each component (per-unit / tiered / volume / package),
  4. adds the plan's recurring flat fee,
  5. optionally pushes the total to Stripe,
  6. persists and returns the Invoice.
"""

from datetime import datetime, timezone

from app.models.billing import Invoice, InvoiceLineItem, new_invoice_id
from app.services import billing_store, meter_store, pricing
from app.services.stripe_client import client as stripe_client


def preview_invoice(subscription_id: str) -> Invoice:
    """Compute an invoice without persisting it or touching Stripe."""
    return _build_invoice(subscription_id)


def generate_invoice(subscription_id: str, push_to_stripe: bool = True) -> Invoice:
    """Compute, optionally bill via Stripe, persist, and return the invoice."""
    invoice = _build_invoice(subscription_id)

    if push_to_stripe and invoice.total_usd > 0:
        customer = billing_store.get_customer(invoice.customer_id)
        stripe_customer_id = (customer.stripe_customer_id if customer else None) or invoice.customer_id
        invoice.stripe_invoice_id = stripe_client.create_invoice(
            stripe_customer_id=stripe_customer_id,
            amount_usd=invoice.total_usd,
            description=f"{invoice.plan_key} — {invoice.period_start} to {invoice.period_end}",
        )

    return billing_store.save_invoice(invoice)


def _build_invoice(subscription_id: str) -> Invoice:
    sub = billing_store.get_subscription(subscription_id)
    if sub is None:
        raise ValueError(f"Unknown subscription '{subscription_id}'")

    plan = billing_store.get_plan(sub.plan_key)
    if plan is None:
        raise ValueError(f"Subscription references unknown plan '{sub.plan_key}'")

    line_items: list[InvoiceLineItem] = []

    if plan.flat_fee_usd > 0:
        line_items.append(InvoiceLineItem(
            description=f"{plan.name} — base fee",
            quantity=1,
            amount_usd=round(plan.flat_fee_usd, 4),
        ))

    for component in plan.components:
        meter = meter_store.get_meter(component.meter_key)
        quantity = meter_store.aggregate(
            customer_id=sub.customer_id,
            meter_key=component.meter_key,
            date_from=sub.period_start,
            date_to=sub.period_end,
        )
        amount = pricing.price_component(quantity, component)
        label = meter.display_name if meter else component.meter_key
        unit = meter.unit if meter else "unit"
        line_items.append(InvoiceLineItem(
            description=f"{label} ({quantity:g} {unit})",
            meter_key=component.meter_key,
            quantity=quantity,
            amount_usd=amount,
        ))

    subtotal = round(sum(li.amount_usd for li in line_items), 2)

    return Invoice(
        id=new_invoice_id(),
        customer_id=sub.customer_id,
        subscription_id=sub.id,
        plan_key=plan.key,
        currency=plan.currency,
        period_start=sub.period_start,
        period_end=sub.period_end,
        line_items=line_items,
        subtotal_usd=subtotal,
        total_usd=subtotal,
        created_at=datetime.now(timezone.utc),
    )
