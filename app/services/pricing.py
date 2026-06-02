"""
Pricing math — pure functions that turn a quantity into a dollar amount.

Four usage-based pricing models, mirroring how Stripe and most billing systems
model metered prices:

  per_unit  flat price per unit
  package   price per block of N units (rounded up — pay for the whole block)
  tiered    graduated: units in each tier billed at that tier's rate (cumulative)
  volume    the entire quantity billed at the single tier it lands in

Tier ladders are ascending by `up_to`; the final tier uses up_to=None (unbounded).
`flat_price_usd` on a tier is a fixed fee charged once if any usage reaches it.
"""

import math

from app.models.billing import PriceComponent, PriceTier, PricingModel


def _price_per_unit(qty: float, component: PriceComponent) -> float:
    return qty * component.unit_price_usd


def _price_package(qty: float, component: PriceComponent) -> float:
    size = component.package_size if component.package_size > 0 else 1.0
    packages = math.ceil(qty / size)
    return packages * component.unit_price_usd


def _price_volume(qty: float, tiers: list[PriceTier]) -> float:
    for tier in tiers:
        if tier.up_to is None or qty <= tier.up_to:
            return qty * tier.unit_price_usd + tier.flat_price_usd
    # qty exceeds every bounded tier and no unbounded tier exists.
    return qty * tiers[-1].unit_price_usd + tiers[-1].flat_price_usd if tiers else 0.0


def _price_tiered(qty: float, tiers: list[PriceTier]) -> float:
    total = 0.0
    lower = 0.0
    for tier in tiers:
        upper = tier.up_to if tier.up_to is not None else qty
        units_in_tier = max(0.0, min(qty, upper) - lower)
        if units_in_tier > 0:
            total += units_in_tier * tier.unit_price_usd + tier.flat_price_usd
        lower = upper
        if tier.up_to is not None and qty <= tier.up_to:
            break
    return total


def price_component(quantity: float, component: PriceComponent) -> float:
    """Compute the charge for one metered component given an aggregated quantity."""
    billable = max(0.0, quantity - component.free_units)
    if billable == 0:
        return 0.0

    if component.pricing_model == PricingModel.PER_UNIT:
        amount = _price_per_unit(billable, component)
    elif component.pricing_model == PricingModel.PACKAGE:
        amount = _price_package(billable, component)
    elif component.pricing_model == PricingModel.VOLUME:
        amount = _price_volume(billable, component.tiers)
    elif component.pricing_model == PricingModel.TIERED:
        amount = _price_tiered(billable, component.tiers)
    else:
        amount = 0.0

    return round(amount, 4)
