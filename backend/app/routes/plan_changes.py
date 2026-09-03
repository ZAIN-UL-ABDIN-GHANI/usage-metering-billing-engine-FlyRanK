"""Proration routes - API endpoints for plan changes with billing adjustments."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant
from app.models_proration import PlanChangeRequest, PlanChangeResponse, ProratedAdjustmentResponse, ProratedAdjustmentListResponse
from app.services.proration_service import ProrationService

router = APIRouter(
    prefix="/plan-changes",
    tags=["plan-changes"],
)


@router.post("", status_code=status.HTTP_200_OK)
async def change_plan(
    request: PlanChangeRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Change tenant's plan with prorated billing.

    **Authentication**: Required (API key)

    Calculates prorated adjustment for mid-cycle plan change and updates subscription.

    Args:
        new_plan_id: ID of new plan
        effective_date: When to apply change (optional, defaults to now)

    Returns:
        Plan change result with proration details

    Raises:
        400: Invalid plan or no active subscription
        401: Unauthorized

    Example:
        POST /plan-changes
        Headers:
          X-API-Key: tenant-id
        Body:
          {
            "new_plan_id": "pro",
            "effective_date": "2026-08-19T12:00:00"
          }
        Response:
          {
            "success": true,
            "subscription_id": "sub_123",
            "old_plan_id": "free",
            "new_plan_id": "pro",
            "proration": {
              "proration_type": "upgrade",
              "credit_cents": 0,
              "charge_cents": 500,
              "net_adjustment_cents": 500
            },
            "charge_amount_cents": 500,
            "charge_amount_dollars": 5.00,
            "message": "Plan upgraded. Charge: $5.00"
          }
    """
    service = ProrationService(db)

    try:
        subscription, adjustment = service.apply_plan_change(
            tenant_id=current_tenant.id,
            new_plan_id=request.new_plan_id,
            change_date=request.effective_date,
        )

        # Build response message
        message = f"Plan changed from {subscription.plan_id} to {request.new_plan_id}."

        charge_cents = None
        charge_dollars = None
        credit_cents = None
        credit_dollars = None

        if adjustment.charge_cents > 0:
            charge_cents = adjustment.charge_cents
            charge_dollars = round(charge_cents / 100, 2)
            message += f" Charge: ${charge_dollars:.2f}"
        elif adjustment.credit_cents > 0:
            credit_cents = adjustment.credit_cents
            credit_dollars = round(credit_cents / 100, 2)
            message += f" Credit: ${credit_dollars:.2f}"
        else:
            message += " No proration adjustment."

        return PlanChangeResponse(
            success=True,
            subscription_id=subscription.id,
            old_plan_id=subscription.plan_id,
            new_plan_id=request.new_plan_id,
            proration=ProratedAdjustmentResponse.model_validate(adjustment),
            message=message,
            charge_amount_cents=charge_cents,
            charge_amount_dollars=charge_dollars,
            credit_amount_cents=credit_cents,
            credit_amount_dollars=credit_dollars,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/adjustments", status_code=status.HTTP_200_OK)
async def list_adjustments(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    List prorated adjustments for tenant (paginated).

    **Authentication**: Required (API key)

    Returns all plan change adjustments with pagination.

    Args:
        limit: Max results per page
        offset: Results to skip

    Returns:
        Paginated list of adjustments

    Raises:
        401: Unauthorized

    Example:
        GET /plan-changes/adjustments?limit=10&offset=0
        Headers:
          X-API-Key: tenant-id
    """
    service = ProrationService(db)
    adjustments, total_count = service.get_tenant_adjustments(
        tenant_id=current_tenant.id,
        limit=limit,
        offset=offset,
    )

    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 0

    return ProratedAdjustmentListResponse(
        adjustments=[ProratedAdjustmentResponse.model_validate(a) for a in adjustments],
        total_count=total_count,
        page=offset // limit + 1,
        page_size=limit,
        total_pages=total_pages,
    )


@router.get("/adjustments/{adjustment_id}", status_code=status.HTTP_200_OK)
async def get_adjustment(
    adjustment_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get proration adjustment details.

    **Authentication**: Required (API key)

    Args:
        adjustment_id: Adjustment ID

    Returns:
        Adjustment details

    Raises:
        401: Unauthorized
        403: Access denied
        404: Not found

    Example:
        GET /plan-changes/adjustments/adj_123
        Headers:
          X-API-Key: tenant-id
    """
    service = ProrationService(db)
    adjustment = service.get_adjustment(adjustment_id)

    if not adjustment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Adjustment not found",
        )

    if adjustment.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return ProratedAdjustmentResponse.model_validate(adjustment)


@router.get("/summary", status_code=status.HTTP_200_OK)
async def get_adjustment_summary(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Get proration adjustment summary for tenant.

    **Authentication**: Required (API key)

    Shows total credits, charges, upgrades, and downgrades.

    Returns:
        Adjustment summary with statistics

    Raises:
        401: Unauthorized

    Example:
        GET /plan-changes/summary
        Headers:
          X-API-Key: tenant-id
        Response:
          {
            "tenant_id": "tenant-id",
            "total_adjustments": 3,
            "upgrades": 2,
            "downgrades": 1,
            "total_credits_cents": 1500,
            "total_charges_cents": 2000,
            "net_adjustment_cents": 500
          }
    """
    service = ProrationService(db)
    summary = service.get_adjustment_summary(current_tenant.id)

    return summary
