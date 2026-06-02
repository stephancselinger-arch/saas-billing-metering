from typing import Optional

from fastapi import APIRouter, HTTPException

from app.models.billing import (
    Customer, CustomerCreate, Plan, PlanCreate,
    Subscription, SubscriptionCreate,
)
from app.services import billing_store
from app.services.stripe_client import client as stripe_client

router = APIRouter(tags=["Customers & Plans"])


# ---- Plans ----------------------------------------------------------------

@router.post("/plans", response_model=Plan, status_code=201)
def create_plan(data: PlanCreate):
    try:
        return billing_store.create_plan(data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/plans", response_model=list[Plan])
def list_plans():
    return billing_store.list_plans()


@router.get("/plans/{plan_key}", response_model=Plan)
def get_plan(plan_key: str):
    plan = billing_store.get_plan(plan_key)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


# ---- Customers ------------------------------------------------------------

@router.post("/customers", response_model=Customer, status_code=201)
def create_customer(data: CustomerCreate):
    stripe_customer_id = stripe_client.create_customer(data.name, data.email)
    return billing_store.create_customer(data, stripe_customer_id=stripe_customer_id)


@router.get("/customers", response_model=list[Customer])
def list_customers():
    return billing_store.list_customers()


@router.get("/customers/{customer_id}", response_model=Customer)
def get_customer(customer_id: str):
    customer = billing_store.get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


# ---- Subscriptions --------------------------------------------------------

@router.post("/subscriptions", response_model=Subscription, status_code=201)
def create_subscription(data: SubscriptionCreate):
    if billing_store.get_customer(data.customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if billing_store.get_plan(data.plan_key) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return billing_store.create_subscription(data)


@router.get("/subscriptions", response_model=list[Subscription])
def list_subscriptions(customer_id: Optional[str] = None):
    return billing_store.list_subscriptions(customer_id=customer_id)


@router.post("/subscriptions/{subscription_id}/cancel", response_model=Subscription)
def cancel_subscription(subscription_id: str):
    sub = billing_store.cancel_subscription(subscription_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub
