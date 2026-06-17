# SaaS Billing & Metering

Usage-based billing and metering service with Stripe integration. Records metered usage events, aggregates them per meter, prices them with per-unit / tiered / volume / package models, and turns a subscription's consumption into an invoice — the metering-to-money path that every usage-priced SaaS needs.

## Features

- **Metering** — define billable meters (`api_calls`, `gb_storage`, `compute_seconds`) with `sum`, `max`, `last`, or `unique` aggregation
- **Idempotent Ingestion** — batch-record usage events; repeated `idempotency_key`s are counted once (safe retries)
- **Four Pricing Models** — `per_unit`, `package` (per block, rounded up), `tiered` (graduated), and `volume` (whole quantity at one tier)
- **Free Tiers & Flat Fees** — per-component free units, per-tier flat fees, and a recurring plan base fee
- **Plans & Subscriptions** — bundle a flat fee with any number of metered components; subscribe customers over a billing period
- **Invoicing** — preview (dry-run) or generate invoices with itemized line items
- **Stripe Integration** — pushes customers, usage, and invoices to Stripe when `STRIPE_API_KEY` is set; runs in deterministic **mock mode** with zero dependencies otherwise

## How It Fits Into the Stack

```
DSP Bidder Engine ─┐
SSP Auction Server ─┼─usage events─▶  SaaS Billing & Metering
Campaign Analytics ─┘                  │  meters + aggregates usage
                                       │  prices + invoices
                                ┌──────▼──────┐
                                │    Stripe    │
                                │ (live / mock)│
                                └─────────────┘
```

Any service that produces metered consumption posts usage events here. This service aggregates them per billing period, prices them against the customer's plan, and bills through Stripe.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8006 --reload
```

API docs: http://localhost:8006/docs

To enable live Stripe calls, export a key (otherwise the service runs in mock mode):

```bash
export STRIPE_API_KEY=sk_test_...
```

## Docker

```bash
docker compose up
```

## API Reference

### Usage & Metering

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/usage/meters` | Define a billable meter |
| `GET` | `/v1/usage/meters` | List meters |
| `POST` | `/v1/usage/events` | Batch-ingest usage events (idempotent) |
| `GET` | `/v1/usage/summary` | Aggregated usage for a customer + meter over a period |

### Customers & Plans

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/plans` | Create a pricing plan |
| `GET` | `/v1/plans` | List plans |
| `POST` | `/v1/customers` | Create a customer (also creates a Stripe customer) |
| `GET` | `/v1/customers` | List customers |
| `POST` | `/v1/subscriptions` | Subscribe a customer to a plan |
| `POST` | `/v1/subscriptions/{id}/cancel` | Cancel a subscription |

### Billing & Invoices

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/billing/subscriptions/{id}/preview` | Dry-run invoice (no persist, no Stripe) |
| `POST` | `/v1/billing/subscriptions/{id}/invoice` | Generate + persist invoice, bill via Stripe |
| `GET` | `/v1/billing/invoices` | List invoices |
| `GET` | `/v1/billing/invoices/{id}` | Get an invoice |

## Pricing Models

| Model | How the quantity is priced | Example |
|-------|----------------------------|---------|
| `per_unit` | flat price × units | $0.002 per API call |
| `package` | price per block of N units, rounded up | $1.00 per 1,000 emails |
| `tiered` | graduated — units in each tier billed at that tier's rate | first 1k @ $0.05, next 9k @ $0.03, rest @ $0.01 |
| `volume` | the whole quantity billed at the single tier it lands in | 5,000 seats → all at the 1k–10k rate |

Each component also supports `free_units` (granted before metered pricing applies), and each tier supports a `flat_price_usd` fee charged once if any usage reaches it.

## Example: Define a Meter

```json
POST /v1/usage/meters
{
  "key": "api_calls",
  "display_name": "API Calls",
  "unit": "calls",
  "aggregation": "sum"
}
```

## Example: Create a Plan

```json
POST /v1/plans
{
  "key": "growth",
  "name": "Growth Plan",
  "flat_fee_usd": 50.00,
  "components": [
    {
      "meter_key": "api_calls",
      "pricing_model": "tiered",
      "free_units": 1000,
      "tiers": [
        { "up_to": 10000, "unit_price_usd": 0.01 },
        { "up_to": null,  "unit_price_usd": 0.005 }
      ]
    }
  ]
}
```

## Example: Record Usage

```json
POST /v1/usage/events
[
  {
    "customer_id": "cus_abc123",
    "meter_key": "api_calls",
    "quantity": 5000,
    "timestamp": "2026-06-01T12:00:00Z",
    "idempotency_key": "ingest-2026-06-01-batch-7"
  }
]
```

## Example: Preview an Invoice

```
GET /v1/billing/subscriptions/sub_abc123/preview
```

```json
{
  "plan_key": "growth",
  "line_items": [
    { "description": "Growth Plan — base fee", "quantity": 1, "amount_usd": 50.00 },
    { "description": "API Calls (5000 calls)", "meter_key": "api_calls", "quantity": 5000, "amount_usd": 40.00 }
  ],
  "subtotal_usd": 90.00,
  "total_usd": 90.00
}
```

> 5,000 calls − 1,000 free = 4,000 billable @ $0.01 = $40.00, plus the $50.00 base fee.

## Running Tests

```bash
PYTHONPATH=. pytest tests/ -v
```

Covers all four pricing models, every aggregation type, idempotent ingestion, and the end-to-end preview/generate invoice flow (including Stripe mock-mode assertions).

## Production Considerations

| Component | Dev (current) | Production |
|-----------|--------------|------------|
| Usage event store | In-memory list | ClickHouse / Timescale (columnar, time-series) |
| Plan / customer store | In-memory dict | PostgreSQL |
| Idempotency keys | In-memory set | Redis (SETNX + TTL) |
| Stripe | Mock unless key set | Live API + webhook reconciliation |
| Invoicing | On-demand | Scheduled period-close job per subscription |

## Tech Stack

- **FastAPI** — async REST, auto OpenAPI docs
- **Pydantic v2** — request/response validation
- **Stripe** — metered billing (optional; mock fallback)
- Python 3.12+

<!-- Last updated: 2026-06-03 -->

<!-- Last updated: 2026-06-05 -->

<!-- Last updated: 2026-06-07 -->

<!-- Last updated: 2026-06-09 -->

<!-- Last updated: 2026-06-11 -->

<!-- Last updated: 2026-06-13 -->

<!-- Last updated: 2026-06-15 -->

<!-- Last updated: 2026-06-17 -->
