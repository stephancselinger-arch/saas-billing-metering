from typing import Optional

from fastapi import APIRouter, HTTPException

from app.models.billing import Invoice
from app.services import billing_engine, billing_store

router = APIRouter(prefix="/billing", tags=["Billing & Invoices"])


@router.get("/subscriptions/{subscription_id}/preview", response_model=Invoice)
def preview_invoice(subscription_id: str):
    try:
        return billing_engine.preview_invoice(subscription_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/subscriptions/{subscription_id}/invoice", response_model=Invoice, status_code=201)
def generate_invoice(subscription_id: str, push_to_stripe: bool = True):
    try:
        return billing_engine.generate_invoice(subscription_id, push_to_stripe=push_to_stripe)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/invoices", response_model=list[Invoice])
def list_invoices(customer_id: Optional[str] = None):
    return billing_store.list_invoices(customer_id=customer_id)


@router.get("/invoices/{invoice_id}", response_model=Invoice)
def get_invoice(invoice_id: str):
    invoice = billing_store.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice
