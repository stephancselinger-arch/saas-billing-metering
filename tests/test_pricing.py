import pytest

from app.models.billing import PriceComponent, PriceTier, PricingModel
from app.services import pricing


def test_per_unit():
    comp = PriceComponent(meter_key="api_calls", pricing_model=PricingModel.PER_UNIT,
                          unit_price_usd=0.002)
    assert pricing.price_component(10_000, comp) == pytest.approx(20.0)


def test_per_unit_with_free_units():
    comp = PriceComponent(meter_key="api_calls", pricing_model=PricingModel.PER_UNIT,
                          unit_price_usd=0.01, free_units=1_000)
    # 2500 used - 1000 free = 1500 billable @ 0.01
    assert pricing.price_component(2_500, comp) == pytest.approx(15.0)


def test_per_unit_below_free_units_is_zero():
    comp = PriceComponent(meter_key="api_calls", unit_price_usd=0.01, free_units=1_000)
    assert pricing.price_component(800, comp) == 0.0


def test_package():
    # $1 per 1000 calls, billed per whole package (rounded up)
    comp = PriceComponent(meter_key="api_calls", pricing_model=PricingModel.PACKAGE,
                          package_size=1_000, unit_price_usd=1.0)
    assert pricing.price_component(2_001, comp) == pytest.approx(3.0)  # 3 packages
    assert pricing.price_component(2_000, comp) == pytest.approx(2.0)


def test_volume():
    # Whole quantity priced at the single tier it lands in.
    tiers = [
        PriceTier(up_to=1_000, unit_price_usd=0.05),
        PriceTier(up_to=10_000, unit_price_usd=0.03),
        PriceTier(up_to=None, unit_price_usd=0.01),
    ]
    comp = PriceComponent(meter_key="seats", pricing_model=PricingModel.VOLUME, tiers=tiers)
    # 5000 lands in the 0.03 tier → all 5000 @ 0.03
    assert pricing.price_component(5_000, comp) == pytest.approx(150.0)
    # 50000 lands in the unbounded 0.01 tier
    assert pricing.price_component(50_000, comp) == pytest.approx(500.0)


def test_tiered_graduated():
    # First 1000 @ 0.05, next 9000 @ 0.03, rest @ 0.01
    tiers = [
        PriceTier(up_to=1_000, unit_price_usd=0.05),
        PriceTier(up_to=10_000, unit_price_usd=0.03),
        PriceTier(up_to=None, unit_price_usd=0.01),
    ]
    comp = PriceComponent(meter_key="api_calls", pricing_model=PricingModel.TIERED, tiers=tiers)
    # 5000 → 1000*0.05 + 4000*0.03 = 50 + 120 = 170
    assert pricing.price_component(5_000, comp) == pytest.approx(170.0)
    # 15000 → 1000*0.05 + 9000*0.03 + 5000*0.01 = 50 + 270 + 50 = 370
    assert pricing.price_component(15_000, comp) == pytest.approx(370.0)


def test_tiered_with_flat_fee_per_tier():
    tiers = [
        PriceTier(up_to=100, unit_price_usd=0.0, flat_price_usd=10.0),
        PriceTier(up_to=None, unit_price_usd=0.50),
    ]
    comp = PriceComponent(meter_key="reports", pricing_model=PricingModel.TIERED, tiers=tiers)
    # 150 → tier1 flat 10 (0 units priced) + 50 units @ 0.50 = 10 + 25 = 35
    assert pricing.price_component(150, comp) == pytest.approx(35.0)


def test_zero_quantity():
    comp = PriceComponent(meter_key="api_calls", unit_price_usd=0.01)
    assert pricing.price_component(0, comp) == 0.0
