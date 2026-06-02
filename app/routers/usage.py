from fastapi import APIRouter, HTTPException
from datetime import date
from typing import Optional

from app.models.metering import Meter, MeterCreate, UsageEventCreate
from app.services import meter_store

router = APIRouter(prefix="/usage", tags=["Usage & Metering"])


@router.post("/meters", response_model=Meter, status_code=201)
def create_meter(data: MeterCreate):
    try:
        return meter_store.create_meter(data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/meters", response_model=list[Meter])
def list_meters():
    return meter_store.list_meters()


@router.post("/events")
def ingest_events(events: list[UsageEventCreate]) -> dict:
    try:
        return meter_store.ingest(events)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/summary")
def usage_summary(
    customer_id: str,
    meter_key: str,
    date_from: date,
    date_to: date,
) -> dict:
    meter = meter_store.get_meter(meter_key)
    if meter is None:
        raise HTTPException(status_code=404, detail=f"Unknown meter_key '{meter_key}'")
    quantity = meter_store.aggregate(customer_id, meter_key, date_from, date_to)
    return {
        "customer_id": customer_id,
        "meter_key": meter_key,
        "aggregation": meter.aggregation,
        "unit": meter.unit,
        "period_start": date_from,
        "period_end": date_to,
        "quantity": quantity,
    }
