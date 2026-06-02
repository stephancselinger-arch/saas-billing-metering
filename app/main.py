from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import usage, customers, billing
from app.services import meter_store
from app.services.stripe_client import client as stripe_client

app = FastAPI(
    title="SaaS Billing & Metering",
    description=(
        "Usage-based billing and metering service. Records metered usage events, "
        "aggregates them per meter, prices them with per-unit / tiered / volume / "
        "package models, and produces invoices — with Stripe integration."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(usage.router, prefix="/v1")
app.include_router(customers.router, prefix="/v1")
app.include_router(billing.router, prefix="/v1")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "total_usage_events": meter_store.total_event_count(),
        "stripe_mode": "live" if stripe_client.live else "mock",
    }
