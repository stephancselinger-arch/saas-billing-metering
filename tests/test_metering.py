import pytest
from datetime import datetime, timezone, date, timedelta

from app.models.metering import MeterCreate, UsageEventCreate, Aggregation
from app.services import meter_store


@pytest.fixture(autouse=True)
def clean_store():
    meter_store.reset()
    yield
    meter_store.reset()


def _ts(days_ago: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def test_create_meter_and_reject_duplicate():
    meter_store.create_meter(MeterCreate(key="api_calls", display_name="API Calls", unit="calls"))
    with pytest.raises(ValueError):
        meter_store.create_meter(MeterCreate(key="api_calls", display_name="dup"))


def test_ingest_rejects_unknown_meter():
    with pytest.raises(ValueError):
        meter_store.ingest([UsageEventCreate(customer_id="cus_1", meter_key="nope", quantity=1)])


def test_idempotent_ingest():
    meter_store.create_meter(MeterCreate(key="api_calls", display_name="API Calls"))
    events = [
        UsageEventCreate(customer_id="cus_1", meter_key="api_calls", quantity=5,
                         idempotency_key="abc", timestamp=_ts()),
        UsageEventCreate(customer_id="cus_1", meter_key="api_calls", quantity=5,
                         idempotency_key="abc", timestamp=_ts()),  # duplicate
    ]
    result = meter_store.ingest(events)
    assert result["accepted"] == 1
    assert result["duplicates"] == 1


def test_aggregate_sum():
    meter_store.create_meter(MeterCreate(key="api_calls", display_name="API Calls",
                                         aggregation=Aggregation.SUM))
    meter_store.ingest([
        UsageEventCreate(customer_id="cus_1", meter_key="api_calls", quantity=100, timestamp=_ts()),
        UsageEventCreate(customer_id="cus_1", meter_key="api_calls", quantity=250, timestamp=_ts()),
    ])
    qty = meter_store.aggregate("cus_1", "api_calls", _today(), _today())
    assert qty == pytest.approx(350)


def test_aggregate_max():
    meter_store.create_meter(MeterCreate(key="peak_storage", display_name="Peak Storage",
                                         unit="GB", aggregation=Aggregation.MAX))
    meter_store.ingest([
        UsageEventCreate(customer_id="cus_1", meter_key="peak_storage", quantity=40, timestamp=_ts()),
        UsageEventCreate(customer_id="cus_1", meter_key="peak_storage", quantity=90, timestamp=_ts()),
        UsageEventCreate(customer_id="cus_1", meter_key="peak_storage", quantity=70, timestamp=_ts()),
    ])
    assert meter_store.aggregate("cus_1", "peak_storage", _today(), _today()) == pytest.approx(90)


def test_aggregate_last():
    meter_store.create_meter(MeterCreate(key="storage", display_name="Storage",
                                         unit="GB", aggregation=Aggregation.LAST))
    meter_store.ingest([
        UsageEventCreate(customer_id="cus_1", meter_key="storage", quantity=10, timestamp=_ts(2)),
        UsageEventCreate(customer_id="cus_1", meter_key="storage", quantity=55, timestamp=_ts(0)),
        UsageEventCreate(customer_id="cus_1", meter_key="storage", quantity=30, timestamp=_ts(1)),
    ])
    assert meter_store.aggregate("cus_1", "storage", _today() - timedelta(days=3), _today()) == pytest.approx(55)


def test_aggregate_unique():
    meter_store.create_meter(MeterCreate(key="mau", display_name="Monthly Active Users",
                                         unit="users", aggregation=Aggregation.UNIQUE,
                                         unique_property="user_id"))
    meter_store.ingest([
        UsageEventCreate(customer_id="cus_1", meter_key="mau", timestamp=_ts(), properties={"user_id": "u1"}),
        UsageEventCreate(customer_id="cus_1", meter_key="mau", timestamp=_ts(), properties={"user_id": "u2"}),
        UsageEventCreate(customer_id="cus_1", meter_key="mau", timestamp=_ts(), properties={"user_id": "u1"}),
    ])
    assert meter_store.aggregate("cus_1", "mau", _today(), _today()) == pytest.approx(2)


def test_aggregate_isolates_customers():
    meter_store.create_meter(MeterCreate(key="api_calls", display_name="API Calls"))
    meter_store.ingest([
        UsageEventCreate(customer_id="cus_1", meter_key="api_calls", quantity=100, timestamp=_ts()),
        UsageEventCreate(customer_id="cus_2", meter_key="api_calls", quantity=999, timestamp=_ts()),
    ])
    assert meter_store.aggregate("cus_1", "api_calls", _today(), _today()) == pytest.approx(100)
