"""
Stripe client wrapper.

Wraps the bits of Stripe this service touches: creating customers, reporting
metered usage, and finalizing invoices. It operates in two modes:

  * Live  — when STRIPE_API_KEY is set, calls go to the real Stripe API.
  * Mock  — with no key (local dev, CI, tests), every call returns a
            deterministic fake id and records the call in `mock_calls` so
            tests can assert what *would* have been sent to Stripe.

This keeps the rest of the codebase free of `if stripe_enabled` checks and
lets the service run end-to-end with zero external dependencies.
"""

import os
import uuid
from typing import Optional

try:
    import stripe  # type: ignore
except ImportError:  # pragma: no cover - stripe is optional at runtime
    stripe = None


class StripeClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else os.getenv("STRIPE_API_KEY", "")
        self.live = bool(self.api_key) and stripe is not None
        self.mock_calls: list[dict] = []
        if self.live:
            stripe.api_key = self.api_key

    # ---- helpers ----------------------------------------------------------

    def _record(self, action: str, **payload) -> None:
        self.mock_calls.append({"action": action, **payload})

    @staticmethod
    def _fake_id(prefix: str) -> str:
        return f"{prefix}_mock_{uuid.uuid4().hex[:14]}"

    # ---- API surface ------------------------------------------------------

    def create_customer(self, name: str, email: Optional[str] = None) -> str:
        if self.live:
            obj = stripe.Customer.create(name=name, email=email)
            return obj.id
        self._record("create_customer", name=name, email=email)
        return self._fake_id("cus")

    def create_subscription(self, stripe_customer_id: str, price_lookup_key: str) -> str:
        if self.live:
            obj = stripe.Subscription.create(
                customer=stripe_customer_id,
                items=[{"price": price_lookup_key}],
            )
            return obj.id
        self._record("create_subscription",
                     customer=stripe_customer_id, price=price_lookup_key)
        return self._fake_id("sub")

    def report_usage(self, subscription_item_id: str, quantity: float, timestamp: int) -> str:
        """Push a metered usage record to Stripe (UsageRecord API)."""
        if self.live:
            obj = stripe.SubscriptionItem.create_usage_record(
                subscription_item_id,
                quantity=int(quantity),
                timestamp=timestamp,
                action="set",
            )
            return obj.id
        self._record("report_usage",
                     subscription_item=subscription_item_id,
                     quantity=quantity, timestamp=timestamp)
        return self._fake_id("mbur")

    def create_invoice(self, stripe_customer_id: str, amount_usd: float,
                       description: str) -> str:
        if self.live:
            stripe.InvoiceItem.create(
                customer=stripe_customer_id,
                amount=int(round(amount_usd * 100)),
                currency="usd",
                description=description,
            )
            obj = stripe.Invoice.create(customer=stripe_customer_id, auto_advance=True)
            return obj.id
        self._record("create_invoice",
                     customer=stripe_customer_id,
                     amount_cents=int(round(amount_usd * 100)),
                     description=description)
        return self._fake_id("in")


# Module-level singleton used by the app. Tests can construct their own.
client = StripeClient()
