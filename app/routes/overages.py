"""Overage routes - API endpoints for overage billing and policies."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant, Plan
from app.models_overage import (
    OverageChargeResponse, OveragePolicyResponse, OveragePolicyUpdate,
    OverageChargeListResponse, OverageSummaryResponse, OverageStatusResponse
)
from app.services.overage_service import OverageService

router = APIRouter(
    prefix="/overages",
    tags=["overages"],
)


@router.post("/check", status_code=status.HTTP_200_OK)
async def check_and_create_overages(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Check for overage usage and create charges.

    **Authentication**: Required (API key)

    Scans current usage and creates OverageCharge records for any
    usage beyond plan quotas.

    Returns:
        List of overage charges created (if any)

    Raises:
        401: Unauthorized

    Example:
        POST /overages/check
        Headers:
          X-API-Key: tenant-id
        Response (200 OK):
          {
            "charges_found": [
              {
                "id": "charge_123",
                "usage_type": "api_calls",
                "overage_quantity": 500,
                "overage_total_cost_cents": 5000,
                "overage_total_cost_dollars": 50.0
              }
            ],
            "total_cost_cents": 5000
          }
    """
    service = OverageService(db)
    charges = service.check_and_create_overage_charges(tenant_id=current_tenant.id)

    total_cost = sum(c.overage_total_cost_cents for c in charges)

    return {
        "charges_found": [
            OverageChargeResponse(
                **{**charge.__dict__, 'overage_total_cost_dollars': round(charge.overage_total_cost_cents / 100, 2)}
            ) for charge in charges
        ],
        "total_cost_cents": total_cost,
        "total_cost_dollars": round(total_cost / 100, 2),
    }


@router.get("/charges", status_code=status.HTTP_200_OK)
async def list_charges(
    billing_period: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    List overage charges for tenant (paginated).

    **Authentication**: Required (API key)

    Returns paginated list of overage charges, optionally filtered by period.

    Args:
        billing_period: Optional filter by period (YYYY-MM)
        limit: Max results per page
        offset: Results to skip

    Returns:
        Paginated list of charges

    Raises:
        401: Unauthorized

    Example:
        GET /overages/charges?billing_period=2026-08&limit=10
        Headers:
          X-API-Key: tenant-id
    """
    service = OverageService(db)
    charges, total_count = service.get_tenant_charges(
        tenant_id=current_tenant.id,
        billing_period=billing_period,
        limit=limit,
        offset=offset,
    )

    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 0

    return OverageChargeListResponse(
        charges=[
            OverageChargeResponse(
                **{**c.__dict__, 'overage_total_cost_dollars': round(c.overage_total_cost_cents / 100, 2)}
            ) for c in charges
        ],
        total_count=total_count,
        page=offset // limit + 1,
        page_size=limit,
        total_pages=total_pages,
    )


@router.get("/charges/{charge_id}", status_code=status.HTTP_200_OK)
async def get_charge(
    charge_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get overage charge details.

    **Authentication**: Required (API key)

    Args:
        charge_id: Charge ID

    Returns:
        Charge details

    Raises:
        401: Unauthorized
        404: Charge not found

    Example:
        GET /overages/charges/charge_123
        Headers:
          X-API-Key: tenant-id
    """
    service = OverageService(db)
    charge = service.get_charge(charge_id)

    if not charge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Charge not found",
        )

    if charge.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return OverageChargeResponse(
        **{**charge.__dict__, 'overage_total_cost_dollars': round(charge.overage_total_cost_cents / 100, 2)}
    )


@router.get("/summary", status_code=status.HTTP_200_OK)
async def get_overage_summary(
    billing_period: Optional[str] = Query(None),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get overage summary for period.

    **Authentication**: Required (API key)

    Shows total overage charges, quantities, and split by type.

    Args:
        billing_period: Optional specific period (default: current)

    Returns:
        Overage summary with statistics

    Raises:
        401: Unauthorized

    Example:
        GET /overages/summary
        Headers:
          X-API-Key: tenant-id
        Response:
          {
            "billing_period": "2026-08",
            "total_overage_charges_cents": 5000,
            "total_overage_charges_dollars": 50.0,
            "total_overage_quantity": 500,
            "api_call_overage_cents": 2000,
            "token_overage_cents": 3000,
            "invoiced_cents": 0,
            "pending_cents": 5000
          }
    """
    service = OverageService(db)
    summary = service.get_period_overage_summary(
        tenant_id=current_tenant.id,
        billing_period=billing_period,
    )

    return summary


@router.get("/status/{subscription_id}", status_code=status.HTTP_200_OK)
async def get_overage_status(
    subscription_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get current overage status for subscription.

    **Authentication**: Required (API key)

    Shows if overages are allowed, current amounts, and if suspension is pending.

    Args:
        subscription_id: Subscription ID

    Returns:
        Current overage status

    Raises:
        401: Unauthorized
        404: Subscription not found

    Example:
        GET /overages/status/sub_123
        Headers:
          X-API-Key: tenant-id
    """
    service = OverageService(db)
    status_info = service.get_overage_status(subscription_id)

    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    return status_info


@router.get("/policies/{plan_id}", status_code=status.HTTP_200_OK)
async def get_plan_policy(
    plan_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get overage policy for plan.

    **Authentication**: Required (API key)

    Args:
        plan_id: Plan ID

    Returns:
        Overage policy configuration

    Raises:
        401: Unauthorized

    Example:
        GET /overages/policies/pro
        Headers:
          X-API-Key: tenant-id
    """
    service = OverageService(db)
    policy = service.get_or_create_policy(plan_id)

    return OveragePolicyResponse.model_validate(policy)


@router.put("/policies/{plan_id}", status_code=status.HTTP_200_OK)
async def update_plan_policy(
    plan_id: str,
    request: OveragePolicyUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Update overage policy for plan.

    **Authentication**: Required (API key)

    Configures overage settings: whether to allow, pricing, and limits.

    Args:
        plan_id: Plan ID
        allows_overage: Allow usage beyond quota
        api_calls_overage_price_cents: Cost per additional API call
        ai_tokens_overage_price_cents: Cost per additional token
        max_overage_amount_cents: Max total charge before suspension
        max_overage_quantity: Max units before suspension
        suspend_on_overage_exceeded: Suspend on limit exceeded

    Returns:
        Updated policy

    Raises:
        401: Unauthorized

    Example:
        PUT /overages/policies/pro
        Headers:
          X-API-Key: tenant-id
        Body:
          {
            "allows_overage": true,
            "api_calls_overage_price_cents": 1,
            "ai_tokens_overage_price_cents": 0.0003,
            "max_overage_amount_cents": 50000
          }
    """
    service = OverageService(db)
    policy = service.update_policy(
        plan_id=plan_id,
        allows_overage=request.allows_overage,
        api_calls_price=request.api_calls_overage_price_cents,
        tokens_price=request.ai_tokens_overage_price_cents,
        max_amount=request.max_overage_amount_cents,
        max_quantity=request.max_overage_quantity,
        suspend_on_exceeded=request.suspend_on_overage_exceeded,
    )

    return OveragePolicyResponse.model_validate(policy)
